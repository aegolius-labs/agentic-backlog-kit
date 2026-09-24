"""Adopt issues a repository already has (R11).

Ingestion handles one structured item at a time and only marked issues are
managed, so before this the kit was usable only on a repository that started
empty.  For a product whose value is managing an existing GitHub backlog, that
is the gate on anyone adopting it.

Adoption is deliberately conservative.  Planning reads and writes nothing.  An
issue the operator does not select is observed and left untouched.  Selecting
one adds the kit's marker to its body, preserving everything already written
there, and records the issue in the manifest so ordinary synchronization takes
over without creating a duplicate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Iterable

from .execution import ApplyReceipt, Journal, failure_hint, receipt, state_fingerprint
from .manifest import ManifestError, validate_manifest
from .sync import ApplyAuthorizationError, extract_guid, extract_item_id


ITEM_ID_PREFIX = "GH-"
DEFAULT_IMPORT_TYPE = "Task"
DEFAULT_IMPORT_MATURITY = "idea"
NEUTRAL_SCORE = 3
MARKER_TEMPLATE = "<!-- agentic-backlog-kit:id={item_id};schema=1 -->"

# GitHub organizations define their own issue types. Only the kit's own
# vocabulary can be planned against, so anything else adopts as the default
# rather than inventing a hierarchy level the manifest does not know.
TYPE_ALIASES = {
    "initiative": "Initiative",
    "epic": "Epic",
    "feature": "Feature",
    "story": "Story",
    "user story": "Story",
    "tech story": "Story",
    "bug": "Bug",
    "defect": "Bug",
    "task": "Task",
    "chore": "Task",
}


@dataclass(frozen=True, slots=True)
class ImportAction:
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
class ImportPlan:
    actions: list[ImportAction]
    items: list[dict[str, Any]]
    digest: str
    manifest_fingerprint: str
    snapshot_fingerprint: str
    skipped: dict[str, str] = field(default_factory=dict)
    infer_relationships: bool = False
    withheld_relationships: dict[str, list[str]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "manifest_fingerprint": self.manifest_fingerprint,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "action_count": len(self.actions),
            "items": self.items,
            "skipped": dict(self.skipped),
            "infer_relationships": self.infer_relationships,
            "withheld_relationships": {
                item_id: list(reasons)
                for item_id, reasons in self.withheld_relationships.items()
            },
            "actions": [action.as_dict() for action in self.actions],
        }


def proposed_item_id(number: int) -> str:
    """Derive a stable id from the issue number.

    The issue number is already unique and permanent within the repository, so
    deriving from it keeps adoption idempotent without a counter that two
    concurrent imports could disagree about.
    """

    return f"{ITEM_ID_PREFIX}{number}"


def _resolve_type(raw: str | None, hierarchy_types: set[str]) -> str:
    if raw:
        mapped = TYPE_ALIASES.get(str(raw).strip().casefold())
        if mapped and mapped in hierarchy_types:
            return mapped
    return DEFAULT_IMPORT_TYPE


def _resolve_status(state: str, workflow: dict[str, Any]) -> str:
    statuses = workflow["statuses"]
    if str(state).casefold() == "closed":
        return workflow["done_statuses"][0]
    for candidate in ("Inbox", "Refining", "Ready"):
        if candidate in statuses:
            return candidate
    return statuses[0]


def _import_description(issue: dict[str, Any]) -> str:
    """Keep what the issue already says, so adoption does not erase it."""

    body = str(issue.get("body") or "")
    cleaned = "\n".join(
        line for line in body.splitlines() if "agentic-backlog-kit:id=" not in line
    ).strip()
    return cleaned or str(issue.get("title") or "").strip() or "Imported issue"


def adopted_body(item_id: str, body: str) -> str:
    """Prepend the marker, preserving every line already written."""

    marker = MARKER_TEMPLATE.format(item_id=item_id)
    existing = str(body or "")
    if existing.strip():
        return f"{marker}\n\n{existing}"
    return marker


def _digest(
    actions: Iterable[ImportAction],
    items: list[dict[str, Any]],
    manifest_fingerprint: str,
    snapshot_fingerprint: str,
) -> str:
    payload = {
        "actions": [action.as_dict() for action in actions],
        "items": items,
        "manifest_fingerprint": manifest_fingerprint,
        "snapshot_fingerprint": snapshot_fingerprint,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reaches(adjacency: dict[str, set[str]], start: str, target: str) -> bool:
    """Whether `target` is reachable from `start` along accepted dependencies."""

    seen: set[str] = set()
    queue = [start]
    while queue:
        current = queue.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        queue.extend(sorted(adjacency.get(current, ())))
    return False


def _resolve_related(
    related: dict[str, Any] | None,
    *,
    existing_ids: set[str],
    adopted_by_number: dict[int, str],
    context: str,
) -> tuple[str | None, str | None]:
    """Map one observed GitHub relationship onto a manifest item id.

    Returns the resolved id, or `None` with the reason it could not be used.
    An issue outside both the manifest and this adoption cannot be referenced:
    the manifest validator rejects an unknown id, so proposing one would make
    the plan unapplyable.
    """

    if related is None:
        return None, None
    number = int(related["number"])
    marker_id = related.get("abk_id")
    if marker_id:
        if marker_id in existing_ids:
            return str(marker_id), None
        return None, (
            f"issue #{number} is marked as '{marker_id}' but the manifest does "
            "not record it; run import-reconcile first"
        )
    adopted = adopted_by_number.get(number)
    if adopted:
        return adopted, None
    return None, (
        f"issue #{number} is neither managed nor part of this {context}"
    )


def _infer_relationships(
    data: dict[str, Any],
    adopted: list[tuple[dict[str, Any], dict[str, Any]]],
    levels: dict[str, int],
    *,
    extra_resolvable_ids: frozenset[str] | set[str] = frozenset(),
    context: str = "adoption",
) -> dict[str, list[str]]:
    """Propose the hierarchy and dependencies GitHub already records.

    `adopted` pairs each observed issue with the item proposed for it, which
    the caller already knows; this mutates those items in place.

    `extra_resolvable_ids` names ids that will exist once this pass is written
    but are not in the manifest yet, and that a relationship can already
    identify by marker. Orphan recovery needs it, because one stranded issue can
    be the parent of another and both carry markers the manifest has not
    recorded. Adoption passes nothing, so an unrecorded marker keeps pointing
    the operator at recovery instead of resolving to a proposal.

    Every relationship this cannot express is dropped and reported rather than
    forced: adoption must succeed against a repository shaped however it is
    shaped, and the manifest's strict ladder and acyclic dependency rule are
    narrower than what GitHub permits.
    """

    existing_ids = {item["id"] for item in data["items"]} | set(extra_resolvable_ids)
    adopted_by_number = {
        int(issue["number"]): item["id"] for issue, item in adopted
    }
    known_types = {
        **{item["id"]: item["type"] for item in data["items"]},
        **{item["id"]: item["type"] for _, item in adopted},
    }
    withheld: dict[str, list[str]] = {}

    def withhold(item_id: str, reason: str) -> None:
        withheld.setdefault(item_id, []).append(reason)

    for issue, item in adopted:
        parent_id, reason = _resolve_related(
            issue.get("parent_issue"),
            existing_ids=existing_ids,
            adopted_by_number=adopted_by_number,
            context=context,
        )
        if reason:
            withhold(item["id"], f"parent: {reason}")
            continue
        if parent_id is None:
            continue
        parent_type = known_types[parent_id]
        if levels[item["type"]] != levels[parent_type] + 1:
            withhold(
                item["id"],
                f"parent: '{parent_id}' is type '{parent_type}' and this item is "
                f"type '{item['type']}', which the hierarchy does not allow",
            )
            continue
        item["parent"] = parent_id

    adjacency: dict[str, set[str]] = {
        existing["id"]: set(existing["depends_on"]) for existing in data["items"]
    }
    for _, item in adopted:
        adjacency.setdefault(item["id"], set())

    for issue, item in adopted:
        accepted: set[str] = set()
        for related in issue.get("blocked_by") or []:
            dependency_id, reason = _resolve_related(
                related,
                existing_ids=existing_ids,
                adopted_by_number=adopted_by_number,
                context=context,
            )
            if reason:
                withhold(item["id"], f"blocked by: {reason}")
                continue
            if dependency_id is None or dependency_id == item["id"]:
                continue
            if _reaches(adjacency, dependency_id, item["id"]):
                withhold(
                    item["id"],
                    f"blocked by: '{dependency_id}' would close a dependency cycle",
                )
                continue
            adjacency[item["id"]].add(dependency_id)
            accepted.add(dependency_id)
        item["depends_on"] = sorted(accepted)

    return {item_id: withheld[item_id] for item_id in sorted(withheld)}


def build_import_plan(
    manifest: dict[str, Any],
    unmanaged_issues: list[dict[str, Any]],
    *,
    include: set[int] | frozenset[int] | None = None,
    limit: int | None = None,
    allow_duplicate_titles: bool = False,
    infer_relationships: bool = False,
) -> ImportPlan:
    """Preview adopting existing issues without reading or writing anything more.

    Nothing here mutates.  The result is a reviewable mapping from issue to
    proposed backlog item, plus the reason every issue that was not proposed
    was left out.
    """

    data = validate_manifest(manifest)
    hierarchy = data["workflow"].get("hierarchy", [])
    hierarchy_types = {level_type for level in hierarchy for level_type in level}
    levels = {
        level_type: index
        for index, level in enumerate(hierarchy)
        for level_type in level
    }
    existing_ids = {item["id"] for item in data["items"]}
    existing_titles = {item["title"].strip().casefold() for item in data["items"]}

    if infer_relationships:
        unread = sorted(
            int(issue["number"])
            for issue in unmanaged_issues
            if "parent_issue" not in issue or "blocked_by" not in issue
        )
        if unread:
            raise ManifestError(
                "Relationship inference needs issues read with relationships; "
                "these carry none: "
                + ", ".join(f"#{number}" for number in unread)
            )

    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
    ):
        raise ManifestError("Import limit must be a positive integer")

    if include is not None:
        known = {int(issue["number"]) for issue in unmanaged_issues}
        missing = sorted(set(include) - known)
        if missing:
            raise ManifestError(
                "Import selection references issues that are not unmanaged: "
                + ", ".join(f"#{number}" for number in missing)
            )

    actions: list[ImportAction] = []
    items: list[dict[str, Any]] = []
    adopted: list[tuple[dict[str, Any], dict[str, Any]]] = []
    skipped: dict[str, str] = {}
    proposed_ids: set[str] = set()

    for issue in sorted(unmanaged_issues, key=lambda value: int(value["number"])):
        number = int(issue["number"])
        key = f"#{number}"
        if include is not None and number not in include:
            skipped[key] = "not selected"
            continue
        if limit is not None and len(items) >= limit:
            skipped[key] = "beyond the requested limit"
            continue

        item_id = proposed_item_id(number)
        if item_id in existing_ids or item_id in proposed_ids:
            # The marker is the only thing that makes an issue managed, so a
            # colliding id means the manifest already claims this issue under a
            # body that no longer carries one. Refuse rather than fork it.
            raise ManifestError(
                f"Import would duplicate item id '{item_id}'; issue {key} is "
                "already claimed by the manifest"
            )

        title = str(issue.get("title") or "").strip()
        if not title:
            skipped[key] = "issue has no title"
            continue
        if not allow_duplicate_titles and title.casefold() in existing_titles:
            skipped[key] = (
                "a managed item already has this title; pass "
                "--allow-duplicate-titles to adopt it anyway"
            )
            continue

        item = {
            "id": item_id,
            "title": title,
            "type": _resolve_type(issue.get("type"), hierarchy_types),
            "description": _import_description(issue),
            "acceptance_criteria": [],
            "parent": None,
            "depends_on": [],
            "impact": NEUTRAL_SCORE,
            "effort": NEUTRAL_SCORE,
            "business_value": NEUTRAL_SCORE,
            "enabler_value": 0,
            "status": _resolve_status(str(issue.get("state", "open")), data["workflow"]),
            "maturity": DEFAULT_IMPORT_MATURITY,
            "sprint": None,
        }
        items.append(item)
        adopted.append((issue, item))
        proposed_ids.add(item_id)
        existing_titles.add(title.casefold())

        observed_body = str(issue.get("body") or "")
        actions.append(
            ImportAction(
                "issue.adopt",
                item_id,
                {
                    "number": number,
                    "body": adopted_body(item_id, observed_body),
                },
                {
                    "issue": {
                        "number": number,
                        "body_sha256": hashlib.sha256(
                            observed_body.encode("utf-8")
                        ).hexdigest(),
                    }
                },
            )
        )

    withheld_relationships: dict[str, list[str]] = {}
    if infer_relationships:
        withheld_relationships = _infer_relationships(data, adopted, levels)

    # Validate the manifest the plan intends to produce before offering it.
    merged = {**data, "items": [*data["items"], *items]}
    validate_manifest(merged)

    manifest_fingerprint = state_fingerprint(data)
    snapshot_fingerprint = state_fingerprint(unmanaged_issues)
    return ImportPlan(
        actions=actions,
        items=items,
        digest=_digest(actions, items, manifest_fingerprint, snapshot_fingerprint),
        manifest_fingerprint=manifest_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
        skipped=skipped,
        infer_relationships=infer_relationships,
        withheld_relationships=withheld_relationships,
    )


def import_plan_from_dict(data: dict[str, Any]) -> ImportPlan:
    if not isinstance(data, dict) or not isinstance(data.get("actions"), list):
        raise ManifestError("Import plan must contain an actions array")
    actions: list[ImportAction] = []
    for index, raw in enumerate(data["actions"]):
        if not isinstance(raw, dict):
            raise ManifestError(f"Import action at index {index} must be an object")
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
            raise ManifestError(f"Import action at index {index} is malformed")
        actions.append(ImportAction(kind, item_id, payload, precondition))

    items = data.get("items")
    digest = data.get("digest")
    manifest_fingerprint = data.get("manifest_fingerprint")
    snapshot_fingerprint = data.get("snapshot_fingerprint")
    if (
        not isinstance(items, list)
        or not isinstance(digest, str)
        or not isinstance(manifest_fingerprint, str)
        or not isinstance(snapshot_fingerprint, str)
        or _digest(actions, items, manifest_fingerprint, snapshot_fingerprint) != digest
    ):
        raise ManifestError("Import plan digest does not match its contents")
    skipped = data.get("skipped") or {}
    if not isinstance(skipped, dict):
        raise ManifestError("Import plan skipped must be an object")
    withheld = data.get("withheld_relationships") or {}
    if not isinstance(withheld, dict):
        raise ManifestError("Import plan withheld_relationships must be an object")
    inferred = data.get("infer_relationships", False)
    if not isinstance(inferred, bool):
        raise ManifestError("Import plan infer_relationships must be true or false")
    return ImportPlan(
        actions=actions,
        items=items,
        digest=digest,
        manifest_fingerprint=manifest_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
        skipped=skipped,
        infer_relationships=inferred,
        withheld_relationships=withheld,
    )


def apply_import_plan(
    plan: ImportPlan,
    *,
    executor: Callable[[ImportAction], Any],
    confirmation: str | None,
    manifest: dict[str, Any] | None = None,
    unmanaged_issues: list[dict[str, Any]] | None = None,
    journal: Journal | None = None,
) -> ApplyReceipt:
    """Adopt exactly the issues the caller reviewed and confirmed."""

    if not confirmation or confirmation != plan.digest:
        raise ApplyAuthorizationError(
            "Apply requires the exact digest of the reviewed import plan"
        )
    if manifest is None or unmanaged_issues is None:
        raise ApplyAuthorizationError(
            "Apply requires a freshly verified manifest and issue listing"
        )
    fresh = build_import_plan(
        manifest,
        unmanaged_issues,
        include={int(action.payload["number"]) for action in plan.actions},
        infer_relationships=plan.infer_relationships,
    )
    if fresh.digest != plan.digest:
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
                hint=failure_hint(action.kind, action.payload, exc),
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


def find_orphans(
    manifest: dict[str, Any], marked_issues: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return marked issues the manifest does not know about.

    Adoption marks the issue before the manifest records it, so an interruption
    between those steps strands the issue: import skips it because it is
    already marked, and synchronization ignores it because no item claims it.
    Naming that state is the first half of being able to repair it.
    """

    known = {item["id"] for item in validate_manifest(manifest)["items"]}
    return [
        issue
        for issue in sorted(marked_issues, key=lambda value: int(value["number"]))
        if issue.get("abk_id") and issue["abk_id"] not in known
    ]


def reconcile_orphans(
    manifest: dict[str, Any],
    marked_issues: list[dict[str, Any]],
    *,
    infer_relationships: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, list[str]]]:
    """Adopt stranded markers into the manifest without touching GitHub.

    The issue already carries the marker, so repair is purely local: build the
    item the interrupted import would have written and record it under the id
    GitHub is already using.

    `infer_relationships` recovers the sub-issue parent and `blocked by` set
    GitHub records for each orphan, under the same rules adoption uses. Without
    it a recovered item claims no structure while GitHub still holds one, and
    because synchronization is additive nothing ever reconciles that - the same
    divergence adoption stopped producing. It stays opt-in on the same terms,
    because it is the same two extra reads per issue.

    Recovery never writes to GitHub either way. GitHub is already correct.
    """

    data = validate_manifest(manifest)
    hierarchy = data["workflow"].get("hierarchy", [])
    hierarchy_types = {level_type for level in hierarchy for level_type in level}
    levels = {
        level_type: index
        for index, level in enumerate(hierarchy)
        for level_type in level
    }
    orphans = find_orphans(data, marked_issues)

    if infer_relationships:
        unread = sorted(
            int(issue["number"])
            for issue in orphans
            if "parent_issue" not in issue or "blocked_by" not in issue
        )
        if unread:
            raise ManifestError(
                "Relationship inference needs issues read with relationships; "
                "these carry none: "
                + ", ".join(f"#{number}" for number in unread)
            )

    recovered: list[dict[str, Any]] = []
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for issue in orphans:
        title = str(issue.get("title") or "").strip()
        item = {
            "id": issue["abk_id"],
            "title": title or issue["abk_id"],
            "type": _resolve_type(issue.get("type"), hierarchy_types),
            "description": _import_description(issue),
            "acceptance_criteria": [],
            "parent": None,
            "depends_on": [],
            "impact": NEUTRAL_SCORE,
            "effort": NEUTRAL_SCORE,
            "business_value": NEUTRAL_SCORE,
            "enabler_value": 0,
            "status": _resolve_status(
                str(issue.get("state", "open")), data["workflow"]
            ),
            "maturity": DEFAULT_IMPORT_MATURITY,
            "sprint": None,
        }
        guid = issue.get("guid") or extract_guid(issue.get("body"))
        if guid:
            # The marker is the only place a lost item's GUID survives, so
            # recovery that dropped it would sever the trace it exists for.
            item["guid"] = guid
        recovered.append(item)
        pairs.append((issue, item))

    if not recovered:
        return data, [], {}

    withheld: dict[str, list[str]] = {}
    if infer_relationships:
        # One stranded issue can be the parent of another, so the ids this pass
        # is about to write must already be resolvable by marker.
        withheld = _infer_relationships(
            data,
            pairs,
            levels,
            extra_resolvable_ids={item["id"] for item in recovered},
            context="recovery",
        )
    return merge_imported_items(data, recovered), recovered, withheld


def merge_imported_items(
    manifest: dict[str, Any], items: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return the manifest with adopted items added, validated before saving."""

    data = validate_manifest(manifest)
    known = {item["id"] for item in data["items"]}
    duplicates = sorted(item["id"] for item in items if item["id"] in known)
    if duplicates:
        raise ManifestError(
            f"Manifest already contains imported items: {', '.join(duplicates)}"
        )
    merged = {**data, "items": [*data["items"], *items]}
    return validate_manifest(merged)


class ImportExecutor:
    """Write the kit's marker into each adopted issue and nothing else."""

    def __init__(self, service: Any) -> None:
        self.service = service

    def __call__(self, action: ImportAction) -> None:
        if action.kind != "issue.adopt":
            raise ManifestError(f"Unsupported import action kind '{action.kind}'")
        self.service.adopt_issue(action.payload["number"], action.payload["body"])


__all__ = [
    "ImportAction",
    "ImportExecutor",
    "ImportPlan",
    "adopted_body",
    "apply_import_plan",
    "build_import_plan",
    "find_orphans",
    "extract_item_id",
    "import_plan_from_dict",
    "merge_imported_items",
    "proposed_item_id",
    "reconcile_orphans",
]
