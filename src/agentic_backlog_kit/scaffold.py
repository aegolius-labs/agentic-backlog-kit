from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Callable, Iterable

from .execution import ApplyReceipt, Journal, receipt, state_fingerprint
from .manifest import ManifestError, validate_manifest
from .views import (
    canonicalize_view,
    expected_view_specs,
    resolve_view_spec,
    semantic_view_configuration,
)


TYPE_LABELS = {
    "type:initiative": ("5319e7", "Portfolio-level outcome"),
    "type:epic": ("8250df", "Large outcome spanning features"),
    "type:feature": ("1d76db", "User-visible capability"),
    "type:story": ("0e8a16", "User-centered deliverable"),
    "type:bug": ("d73a4a", "Defect or regression"),
    "type:task": ("bfdadc", "Implementation work item"),
}

OPTION_PALETTE = (
    "GRAY",
    "BLUE",
    "YELLOW",
    "ORANGE",
    "GREEN",
    "PURPLE",
    "PINK",
    "RED",
)


class ScaffoldAuthorizationError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class ScaffoldAction:
    kind: str
    payload: dict[str, Any]
    precondition: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "payload": self.payload,
            "precondition": self.precondition,
        }


@dataclass(frozen=True, slots=True)
class ScaffoldPlan:
    actions: list[ScaffoldAction]
    digest: str
    manifest_fingerprint: str
    snapshot_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "manifest_fingerprint": self.manifest_fingerprint,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "action_count": len(self.actions),
            "actions": [action.as_dict() for action in self.actions],
        }


def _digest(
    actions: Iterable[ScaffoldAction],
    manifest_fingerprint: str,
    snapshot_fingerprint: str,
) -> str:
    canonical = json.dumps(
        {
            "actions": [action.as_dict() for action in actions],
            "manifest_fingerprint": manifest_fingerprint,
            "snapshot_fingerprint": snapshot_fingerprint,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _iteration(workflow: dict[str, Any]) -> dict[str, Any]:
    iteration = workflow.get("iteration")
    if not isinstance(iteration, dict):
        raise ManifestError(
            "workflow.iteration must configure field, start_date, and duration_days"
        )
    field = iteration.get("field")
    start_date = iteration.get("start_date")
    duration = iteration.get("duration_days")
    if not isinstance(field, str) or not field.strip():
        raise ManifestError("workflow.iteration.field must be a non-empty string")
    try:
        date.fromisoformat(start_date)
    except (TypeError, ValueError) as exc:
        raise ManifestError("workflow.iteration.start_date must use YYYY-MM-DD") from exc
    if isinstance(duration, bool) or not isinstance(duration, int) or duration < 1:
        raise ManifestError("workflow.iteration.duration_days must be a positive integer")
    return {
        "field": field.strip(),
        "start_date": start_date,
        "duration_days": duration,
    }


def _option_names(field: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for option in field.get("options", []):
        result.append(option.get("name") if isinstance(option, dict) else option)
    return result


def _extended_options(
    field: dict[str, Any], missing_options: list[str]
) -> list[dict[str, Any]]:
    """Preserve existing option identities while adding required values."""

    existing: list[dict[str, Any]] = []
    for raw in field.get("options", []):
        if not isinstance(raw, dict) or not raw.get("id") or not raw.get("name"):
            raise ManifestError(
                f"Project field '{field.get('name')}' option metadata is incomplete; "
                "refusing an update that could clear existing values"
            )
        existing.append(
            {
                "id": str(raw["id"]),
                "name": str(raw["name"]),
                "color": str(raw.get("color") or "GRAY"),
                "description": str(raw.get("description") or ""),
            }
        )
    for index, option in enumerate(missing_options, start=len(existing)):
        existing.append(
            {
                "name": option,
                "color": OPTION_PALETTE[index % len(OPTION_PALETTE)],
                "description": "",
            }
        )
    return existing


def build_scaffold_plan(
    manifest: dict[str, Any], project_snapshot: dict[str, Any]
) -> ScaffoldPlan:
    """Describe missing GitHub Project fields, labels, and Agile views."""

    data = validate_manifest(manifest)
    iteration = _iteration(data["workflow"])
    if not isinstance(project_snapshot, dict):
        raise ManifestError("Scaffold snapshot must be an object")
    for key in ("fields", "views", "labels"):
        if not isinstance(project_snapshot.get(key, []), list):
            raise ManifestError(f"Scaffold snapshot {key} must be an array")

    expected_fields = [
        {
            "name": "Status",
            "data_type": "SINGLE_SELECT",
            "options": data["workflow"]["statuses"],
        },
        {
            "name": iteration["field"],
            "data_type": "ITERATION",
            "start_date": iteration["start_date"],
            "duration_days": iteration["duration_days"],
        },
        {"name": "Impact", "data_type": "NUMBER"},
        {"name": "Effort", "data_type": "NUMBER"},
        {"name": "Business Value", "data_type": "NUMBER"},
        {"name": "Enabler Value", "data_type": "NUMBER"},
        {"name": "Priority", "data_type": "NUMBER"},
    ]

    fields_by_name = {
        field.get("name"): field
        for field in project_snapshot.get("fields", [])
        if isinstance(field, dict) and field.get("name")
    }
    field_actions: list[ScaffoldAction] = []
    for expected in expected_fields:
        current = fields_by_name.get(expected["name"])
        if current is None:
            field_actions.append(
                ScaffoldAction(
                    "project.field.create", expected, {"field": None}
                )
            )
            continue
        current_type = current.get("data_type") or current.get("dataType")
        if current_type != expected["data_type"]:
            raise ManifestError(
                f"Project field '{expected['name']}' has type {current_type}; "
                f"expected {expected['data_type']}"
            )
        if expected["data_type"] == "SINGLE_SELECT":
            missing_options = [
                option
                for option in expected["options"]
                if option not in _option_names(current)
            ]
            if missing_options:
                field_id = current.get("id")
                if not field_id:
                    raise ManifestError(
                        f"Project field '{expected['name']}' has no GraphQL id; "
                        "cannot safely add options"
                    )
                field_actions.append(
                    ScaffoldAction(
                        "project.field.update_options",
                        {
                            "name": expected["name"],
                            "field_id": field_id,
                            "options": _extended_options(current, missing_options),
                        },
                        {"field": current},
                    )
                )

    label_names = {
        label.get("name")
        for label in project_snapshot.get("labels", [])
        if isinstance(label, dict)
    }
    label_actions = [
        ScaffoldAction(
            "repository.label.create",
            {"name": name, "color": color, "description": description},
            {"label": None},
        )
        for name, (color, description) in TYPE_LABELS.items()
        if name not in label_names
    ]

    expected_views = expected_view_specs(iteration["field"])
    views_by_name: dict[str, dict[str, Any]] = {}
    for raw_view in project_snapshot.get("views", []):
        current = canonicalize_view(raw_view)
        if current["name"] in views_by_name:
            raise ManifestError(
                f"Project has multiple views named '{current['name']}'; "
                "managed view selection is ambiguous"
            )
        views_by_name[current["name"]] = current
    view_actions: list[ScaffoldAction] = []
    for spec in expected_views:
        current = views_by_name.get(spec["name"])
        expected = resolve_view_spec(
            spec, project_snapshot.get("fields", []), require_ids=False
        )
        if current is None:
            view_actions.append(
                ScaffoldAction("project.view.create", expected, {"view": None})
            )
            continue

        current_semantics = semantic_view_configuration(current)
        expected_semantics = semantic_view_configuration(expected)
        unsupported_drift = [
            key
            for key in ("group_by", "vertical_group_by", "sort_by")
            if current_semantics[key] != expected_semantics[key]
        ]
        if unsupported_drift:
            raise ManifestError(
                f"Project view '{expected['name']}' has unsupported configuration drift "
                f"in {', '.join(unsupported_drift)}; it cannot update grouping or sorting "
                "safely with the current GitHub API. Repair the view in GitHub, refresh, "
                "and re-plan"
            )

        supported_keys = ["layout", "filter"]
        # GitHub documents visible fields as inapplicable to roadmap views.
        if expected_semantics["layout"] != "roadmap":
            supported_keys.append("visible_fields")
        supported_drift = any(
            current_semantics[key] != expected_semantics[key]
            for key in supported_keys
        )
        if supported_drift:
            if not current.get("id"):
                raise ManifestError(
                    f"Project view '{expected['name']}' has no GraphQL id; "
                    "cannot safely update its configuration"
                )
            view_actions.append(
                ScaffoldAction(
                    "project.view.update",
                    {"view_id": current["id"], **expected},
                    {"view": current},
                )
            )

    actions = field_actions + label_actions + view_actions
    manifest_fingerprint = state_fingerprint(data)
    snapshot_fingerprint = state_fingerprint(project_snapshot)
    return ScaffoldPlan(
        actions=actions,
        digest=_digest(actions, manifest_fingerprint, snapshot_fingerprint),
        manifest_fingerprint=manifest_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
    )


def apply_scaffold_plan(
    plan: ScaffoldPlan,
    *,
    executor: Callable[[ScaffoldAction], Any],
    confirmation: str | None,
    manifest: dict[str, Any] | None = None,
    project_snapshot: dict[str, Any] | None = None,
    journal: Journal | None = None,
) -> ApplyReceipt:
    if not confirmation or confirmation != plan.digest:
        raise ScaffoldAuthorizationError(
            "Scaffold apply requires the exact reviewed plan digest"
        )
    if _digest(
        plan.actions, plan.manifest_fingerprint, plan.snapshot_fingerprint
    ) != plan.digest:
        raise ScaffoldAuthorizationError("Scaffold plan changed after validation")
    if manifest is None or project_snapshot is None:
        raise ScaffoldAuthorizationError(
            "Scaffold apply requires a freshly verified manifest and remote snapshot"
        )
    fresh_plan = build_scaffold_plan(manifest, project_snapshot)
    if fresh_plan.digest != plan.digest:
        raise ScaffoldAuthorizationError(
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


def scaffold_plan_from_dict(data: dict[str, Any]) -> ScaffoldPlan:
    if not isinstance(data, dict) or not isinstance(data.get("actions"), list):
        raise ManifestError("Scaffold plan must contain an actions array")
    actions: list[ScaffoldAction] = []
    for index, raw in enumerate(data["actions"]):
        if not isinstance(raw, dict):
            raise ManifestError(f"Scaffold action at index {index} must be an object")
        kind = raw.get("kind")
        payload = raw.get("payload")
        precondition = raw.get("precondition")
        if (
            not isinstance(kind, str)
            or not isinstance(payload, dict)
            or not isinstance(precondition, dict)
        ):
            raise ManifestError(f"Scaffold action at index {index} is malformed")
        actions.append(ScaffoldAction(kind, payload, precondition))
    digest = data.get("digest")
    manifest_fingerprint = data.get("manifest_fingerprint")
    snapshot_fingerprint = data.get("snapshot_fingerprint")
    if (
        not isinstance(digest, str)
        or not isinstance(manifest_fingerprint, str)
        or not isinstance(snapshot_fingerprint, str)
        or _digest(actions, manifest_fingerprint, snapshot_fingerprint) != digest
    ):
        raise ManifestError("Scaffold plan digest does not match its actions")
    return ScaffoldPlan(
        actions=actions,
        digest=digest,
        manifest_fingerprint=manifest_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
    )
