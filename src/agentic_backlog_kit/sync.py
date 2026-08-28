from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Iterable

from .execution import ApplyReceipt, Journal, receipt, state_fingerprint
from .manifest import ManifestError, validate_manifest
from .priority import prioritize


class ApplyAuthorizationError(PermissionError):
    """Raised when apply is attempted without confirming the exact plan digest."""


@dataclass(frozen=True, slots=True)
class SyncAction:
    kind: str
    item_id: str
    payload: dict[str, Any]
    precondition: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "item_id": self.item_id,
            "payload": self.payload,
            "precondition": self.precondition,
        }


@dataclass(frozen=True, slots=True)
class SyncPlan:
    actions: list[SyncAction]
    digest: str
    manifest_fingerprint: str
    snapshot_fingerprint: str
    manage_body: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "manifest_fingerprint": self.manifest_fingerprint,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "manage_body": self.manage_body,
            "action_count": len(self.actions),
            "actions": [action.as_dict() for action in self.actions],
        }


def render_issue_body(item: dict[str, Any]) -> str:
    criteria = "\n".join(
        f"- [ ] {criterion}" for criterion in item["acceptance_criteria"]
    )
    dependencies = ", ".join(item["depends_on"]) or "None"
    parent = item["parent"] or "None"
    return (
        f"<!-- agentic-backlog-kit:id={item['id']};schema=1 -->\n\n"
        f"## Outcome\n\n{item['description']}\n\n"
        f"## Acceptance criteria\n\n{criteria or '- [ ] Define acceptance criteria'}\n\n"
        "## Backlog metadata\n\n"
        f"- Type: {item['type']}\n"
        f"- Parent: {parent}\n"
        f"- Depends on: {dependencies}\n"
    )


def extract_item_id(body: str | None) -> str | None:
    marker = "<!-- agentic-backlog-kit:id="
    if not body or marker not in body:
        return None
    value = body.split(marker, 1)[1].split(";", 1)[0].strip()
    return value or None


def _desired_fields(
    item: dict[str, Any], priority_score: float, *, sprint_field: str
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "Status": item["status"],
        "Impact": item["impact"],
        "Effort": item["effort"],
        "Business Value": item["business_value"],
        "Enabler Value": item["enabler_value"],
        "Priority": priority_score,
    }
    if item.get("sprint"):
        if item["sprint"] in {"@current", "@next"}:
            raise ManifestError(
                f"Item '{item['id']}' sprint alias must be resolved to an exact "
                "active iteration title before synchronization"
            )
        fields[sprint_field] = item["sprint"]
    return fields


def _normalize_remote(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("issues", []), list):
        raise ManifestError("Remote snapshot must contain an issues array")
    remote_by_id: dict[str, dict[str, Any]] = {}
    for index, issue in enumerate(snapshot.get("issues", [])):
        if not isinstance(issue, dict):
            raise ManifestError(f"Remote issue at index {index} must be an object")
        item_id = issue.get("abk_id") or extract_item_id(issue.get("body"))
        if not item_id:
            continue
        if item_id in remote_by_id:
            raise ManifestError(f"Remote snapshot contains duplicate ABK id '{item_id}'")
        remote_by_id[item_id] = issue
    return remote_by_id


def _plan_digest(
    actions: Iterable[SyncAction],
    manifest_fingerprint: str,
    snapshot_fingerprint: str,
    manage_body: bool,
) -> str:
    payload = {
        "actions": [action.as_dict() for action in actions],
        "manifest_fingerprint": manifest_fingerprint,
        "snapshot_fingerprint": snapshot_fingerprint,
        "manage_body": manage_body,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_sync_plan(
    manifest: dict[str, Any],
    remote_snapshot: dict[str, Any],
    *,
    manage_body: bool = True,
) -> SyncPlan:
    """Build an idempotent local-to-GitHub plan without performing mutations."""

    data = validate_manifest(manifest)
    remote_by_id = _normalize_remote(remote_snapshot)
    local_by_id = {item["id"]: item for item in data["items"]}
    score_by_id = {entry.id: entry.priority_score for entry in prioritize(data)}
    iteration = data["workflow"].get("iteration") or {}
    sprint_field = iteration.get("field", "Sprint")

    creates: list[SyncAction] = []
    updates: list[SyncAction] = []
    project_actions: list[SyncAction] = []
    relationship_actions: list[SyncAction] = []

    for item_id in sorted(local_by_id):
        item = local_by_id[item_id]
        remote = remote_by_id.get(item_id)
        desired_body = render_issue_body(item)
        desired_fields = _desired_fields(
            item, score_by_id[item_id], sprint_field=sprint_field
        )

        if remote is None:
            creates.append(
                SyncAction(
                    "issue.create",
                    item_id,
                    {
                        "title": item["title"],
                        "body": desired_body,
                        "type": item["type"],
                        "fallback_label": f"type:{item['type'].lower()}",
                    },
                    {"issue": None},
                )
            )
            project_actions.append(
                SyncAction(
                    "project.add_item",
                    item_id,
                    {"fields": desired_fields},
                    {"issue": None, "requires": "issue.create"},
                )
            )
        else:
            issue_changes: dict[str, Any] = {}
            if remote.get("title") != item["title"]:
                issue_changes["title"] = item["title"]
            if manage_body and remote.get("body", "") != desired_body:
                issue_changes["body"] = desired_body
            if remote.get("type") != item["type"]:
                issue_changes["type"] = item["type"]
                fallback_label = f"type:{item['type'].lower()}"
                issue_changes["fallback_label"] = fallback_label
                if isinstance(remote.get("labels"), list):
                    unmanaged_labels = sorted(
                        {
                            label
                            for label in remote["labels"]
                            if isinstance(label, str)
                            and not label.casefold().startswith("type:")
                        }
                    )
                    issue_changes["labels"] = unmanaged_labels + [fallback_label]
            if issue_changes:
                updates.append(
                    SyncAction("issue.update", item_id, issue_changes, {"issue": remote})
                )

            if not remote.get("in_project", False):
                project_actions.append(
                    SyncAction(
                        "project.add_item",
                        item_id,
                        {"fields": desired_fields},
                        {"issue": remote},
                    )
                )
            else:
                current_fields = remote.get("project_fields") or {}
                changed_fields = {
                    name: value
                    for name, value in desired_fields.items()
                    if current_fields.get(name) != value
                }
                if changed_fields:
                    project_actions.append(
                        SyncAction(
                            "project.set_fields",
                            item_id,
                            {"fields": changed_fields},
                            {"issue": remote},
                        )
                    )

        current_parent = remote.get("parent_abk_id") if remote else None
        if item["parent"] and current_parent != item["parent"]:
            relationship_actions.append(
                SyncAction(
                    "issue.set_parent",
                    item_id,
                    {"parent": item["parent"]},
                    {"issue": remote},
                )
            )

        current_dependencies = set(
            remote.get("depends_on_abk_ids", []) if remote else []
        )
        for dependency in sorted(set(item["depends_on"]) - current_dependencies):
            relationship_actions.append(
                SyncAction(
                    "issue.add_dependency",
                    item_id,
                    {"depends_on": dependency},
                    {"issue": remote},
                )
            )

    actions = creates + updates + project_actions + relationship_actions
    manifest_fingerprint = state_fingerprint(data)
    snapshot_fingerprint = state_fingerprint(remote_snapshot)
    return SyncPlan(
        actions=actions,
        digest=_plan_digest(
            actions, manifest_fingerprint, snapshot_fingerprint, manage_body
        ),
        manifest_fingerprint=manifest_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
        manage_body=manage_body,
    )


def apply_plan(
    plan: SyncPlan,
    *,
    executor: Callable[[SyncAction], Any],
    confirmation: str | None,
    manifest: dict[str, Any] | None = None,
    remote_snapshot: dict[str, Any] | None = None,
    journal: Journal | None = None,
) -> ApplyReceipt:
    """Execute only the exact plan the caller reviewed and confirmed."""

    if not confirmation or confirmation != plan.digest:
        raise ApplyAuthorizationError(
            "Apply requires the exact digest of the reviewed sync plan"
        )
    if _plan_digest(
        plan.actions,
        plan.manifest_fingerprint,
        plan.snapshot_fingerprint,
        plan.manage_body,
    ) != plan.digest:
        raise ApplyAuthorizationError("Sync plan changed after validation")
    if manifest is None or remote_snapshot is None:
        raise ApplyAuthorizationError(
            "Apply requires a freshly verified manifest and remote snapshot"
        )
    fresh_plan = build_sync_plan(
        manifest, remote_snapshot, manage_body=plan.manage_body
    )
    if fresh_plan.digest != plan.digest:
        raise ApplyAuthorizationError(
            "Local or remote state drifted after review; rebuild and reconfirm the plan"
        )

    started_at = datetime.now(UTC).isoformat()
    completed: list[dict[str, Any]] = []
    current = receipt(
        plan.digest,
        plan.manifest_fingerprint,
        plan.snapshot_fingerprint,
        "running",
        len(plan.actions),
        completed,
        started_at,
    )
    if journal:
        journal(current)
    for action in plan.actions:
        try:
            executor(action)
        except Exception as exc:
            current = receipt(
                plan.digest,
                plan.manifest_fingerprint,
                plan.snapshot_fingerprint,
                "failed",
                len(plan.actions),
                completed,
                started_at,
                failed_action=action.as_dict(),
                error=f"{type(exc).__name__}: {exc}",
            )
            if journal:
                journal(current)
            raise
        completed.append(action.as_dict())
        current = receipt(
            plan.digest,
            plan.manifest_fingerprint,
            plan.snapshot_fingerprint,
            "running",
            len(plan.actions),
            completed,
            started_at,
        )
        if journal:
            journal(current)
    current = receipt(
        plan.digest,
        plan.manifest_fingerprint,
        plan.snapshot_fingerprint,
        "completed",
        len(plan.actions),
        completed,
        started_at,
    )
    if journal:
        journal(current)
    return current


def sync_plan_from_dict(data: dict[str, Any]) -> SyncPlan:
    if not isinstance(data, dict) or not isinstance(data.get("actions"), list):
        raise ManifestError("Sync plan must contain an actions array")
    actions: list[SyncAction] = []
    for index, raw in enumerate(data["actions"]):
        if not isinstance(raw, dict):
            raise ManifestError(f"Sync action at index {index} must be an object")
        kind = raw.get("kind")
        item_id = raw.get("item_id")
        payload = raw.get("payload")
        precondition = raw.get("precondition")
        if (
            not isinstance(kind, str)
            or not isinstance(item_id, str)
            or not isinstance(payload, dict)
            or not isinstance(precondition, dict)
        ):
            raise ManifestError(f"Sync action at index {index} is malformed")
        actions.append(SyncAction(kind, item_id, payload, precondition))
    digest = data.get("digest")
    manifest_fingerprint = data.get("manifest_fingerprint")
    snapshot_fingerprint = data.get("snapshot_fingerprint")
    manage_body = data.get("manage_body")
    if (
        not isinstance(digest, str)
        or not isinstance(manifest_fingerprint, str)
        or not isinstance(snapshot_fingerprint, str)
        or not isinstance(manage_body, bool)
        or _plan_digest(
            actions, manifest_fingerprint, snapshot_fingerprint, manage_body
        )
        != digest
    ):
        raise ManifestError("Sync plan digest does not match its actions")
    return SyncPlan(
        actions=actions,
        digest=digest,
        manifest_fingerprint=manifest_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
        manage_body=manage_body,
    )
