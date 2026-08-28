from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Callable, Iterable

from .execution import ApplyReceipt, Journal, receipt, state_fingerprint
from .manifest import ManifestError, validate_manifest


_NUMBERED_TITLE = re.compile(r"^(?P<prefix>.*?)(?P<number>\d+)$")


class IterationAuthorizationError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class IterationAction:
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
class IterationPlan:
    target: str
    as_of: str
    resolved_title: str
    resolved_iteration_id: str | None
    actions: list[IterationAction]
    digest: str
    manifest_fingerprint: str
    snapshot_fingerprint: str

    @property
    def ready(self) -> bool:
        return not self.actions and self.resolved_iteration_id is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "as_of": self.as_of,
            "resolved_title": self.resolved_title,
            "resolved_iteration_id": self.resolved_iteration_id,
            "ready": self.ready,
            "digest": self.digest,
            "manifest_fingerprint": self.manifest_fingerprint,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "action_count": len(self.actions),
            "actions": [action.as_dict() for action in self.actions],
        }


def _parse_date(value: Any, label: str) -> date:
    if not isinstance(value, str):
        raise ManifestError(f"{label} must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ManifestError(f"{label} must use YYYY-MM-DD") from exc


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ManifestError(f"{label} must be a positive integer")
    return value


def _entry(raw: Any, *, completed: bool, index: int) -> dict[str, Any]:
    label = "completed iteration" if completed else "active iteration"
    if not isinstance(raw, dict):
        raise ManifestError(f"Project {label} at index {index} must be an object")
    identifier = raw.get("id")
    title = raw.get("title")
    start = raw.get("start_date", raw.get("startDate"))
    duration = raw.get("duration_days", raw.get("duration"))
    if not isinstance(identifier, str) or not identifier:
        raise ManifestError(f"Project {label} '{title or index}' has no iteration id")
    if not isinstance(title, str) or not title.strip():
        raise ManifestError(f"Project {label} at index {index} has no title")
    start_value = _parse_date(start, f"Project iteration '{title}' start_date")
    duration_value = _positive_int(
        duration, f"Project iteration '{title}' duration_days"
    )
    return {
        "id": identifier,
        "title": title.strip(),
        "start_date": start_value.isoformat(),
        "duration_days": duration_value,
        "completed": completed,
    }


def _validate_entries(entries: Iterable[dict[str, Any]]) -> None:
    ordered = sorted(entries, key=lambda item: (item["start_date"], item["title"], item["id"]))
    ids: set[str] = set()
    titles: set[str] = set()
    previous: dict[str, Any] | None = None
    for item in ordered:
        if item["id"] in ids:
            raise ManifestError(f"Project iteration id '{item['id']}' is duplicated")
        if item["title"] in titles:
            raise ManifestError(
                f"Project iteration has duplicate title '{item['title']}'"
            )
        ids.add(item["id"])
        titles.add(item["title"])
        if previous is not None:
            previous_end = _parse_date(
                previous["start_date"], "Project iteration start_date"
            ) + timedelta(days=previous["duration_days"])
            current_start = _parse_date(item["start_date"], "Project iteration start_date")
            if current_start < previous_end:
                raise ManifestError(
                    f"Project iterations '{previous['title']}' and '{item['title']}' overlap"
                )
        previous = item


def normalize_iteration_field(raw_field: dict[str, Any]) -> dict[str, Any]:
    """Return the compact, canonical Project iteration field contract.

    GitHub exposes completed and non-completed entries separately and uses
    camelCase names. Local snapshots retain that distinction explicitly so a
    plan cannot silently target a completed iteration.
    """

    if not isinstance(raw_field, dict):
        raise ManifestError("Project iteration field must be an object")
    data_type = raw_field.get("data_type", raw_field.get("dataType"))
    if data_type != "ITERATION":
        raise ManifestError("Project iteration field must have type ITERATION")
    identifier = raw_field.get("id")
    name = raw_field.get("name")
    if not isinstance(identifier, str) or not identifier:
        raise ManifestError("Project iteration field has no GraphQL id")
    if not isinstance(name, str) or not name.strip():
        raise ManifestError("Project iteration field has no name")

    configuration = raw_field.get("iteration_configuration")
    if configuration is None:
        configuration = raw_field.get("configuration")
    if not isinstance(configuration, dict):
        raise ManifestError(f"Project iteration field '{name}' has no configuration")

    duration = _positive_int(
        configuration.get("duration_days", configuration.get("duration")),
        f"Project iteration field '{name}' duration_days",
    )
    active = [
        _entry(item, completed=False, index=index)
        for index, item in enumerate(configuration.get("iterations") or [])
    ]
    completed = [
        _entry(item, completed=True, index=index)
        for index, item in enumerate(
            configuration.get(
                "completed_iterations", configuration.get("completedIterations")
            )
            or []
        )
    ]
    _validate_entries([*active, *completed])
    active.sort(key=lambda item: (item["start_date"], item["title"], item["id"]))
    completed.sort(key=lambda item: (item["start_date"], item["title"], item["id"]))

    start = configuration.get("start_date", configuration.get("startDate"))
    if start is None:
        known = [*active, *completed]
        if not known:
            raise ManifestError(
                f"Project iteration field '{name}' has no schedule start or iterations"
            )
        start = min(item["start_date"] for item in known)
    start_value = _parse_date(start, f"Project iteration field '{name}' start_date")

    return {
        "id": identifier,
        "database_id": raw_field.get("database_id", raw_field.get("databaseId")),
        "name": name.strip(),
        "data_type": "ITERATION",
        "iteration_configuration": {
            "start_date": start_value.isoformat(),
            "duration_days": duration,
            "iterations": active,
            "completed_iterations": completed,
        },
    }


def discover_iterations(
    field: dict[str, Any], *, as_of: str | date | None = None
) -> dict[str, Any]:
    normalized = normalize_iteration_field(field)
    selected_date = date.today() if as_of is None else (
        as_of if isinstance(as_of, date) else _parse_date(as_of, "as_of")
    )
    configuration = normalized["iteration_configuration"]
    active = configuration["iterations"]
    current = [
        item
        for item in active
        if _parse_date(item["start_date"], "iteration start_date")
        <= selected_date
        < _parse_date(item["start_date"], "iteration start_date")
        + timedelta(days=item["duration_days"])
    ]
    if len(current) > 1:
        raise ManifestError(
            f"Project iteration field '{normalized['name']}' has ambiguous current iterations"
        )
    upcoming = [
        item
        for item in active
        if _parse_date(item["start_date"], "iteration start_date") > selected_date
    ]
    return {
        "field": normalized,
        "as_of": selected_date.isoformat(),
        "completed": list(configuration["completed_iterations"]),
        "current": current[0] if current else None,
        "upcoming": upcoming,
    }


def _iteration_config(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    data = validate_manifest(manifest)
    configuration = data["workflow"].get("iteration")
    if not isinstance(configuration, dict):
        raise ManifestError(
            "workflow.iteration must configure field, start_date, and duration_days"
        )
    return data, configuration


def _find_field(snapshot: dict[str, Any], name: str) -> dict[str, Any]:
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("fields"), list):
        raise ManifestError("Iteration planning requires a Project scaffold snapshot")
    matches = [
        field
        for field in snapshot["fields"]
        if isinstance(field, dict) and field.get("name") == name
    ]
    if len(matches) != 1:
        if not matches:
            raise ManifestError(f"Project iteration field '{name}' does not exist")
        raise ManifestError(f"Project iteration field '{name}' is ambiguous")
    return normalize_iteration_field(matches[0])


def _increment_title(title: str, amount: int = 1) -> str:
    match = _NUMBERED_TITLE.fullmatch(title)
    if not match:
        raise ManifestError(
            f"Cannot safely derive the next iteration title from '{title}'; "
            "use a numeric suffix"
        )
    raw_number = match.group("number")
    number = int(raw_number) + amount
    rendered = str(number).zfill(len(raw_number))
    return f"{match.group('prefix')}{rendered}"


def _new_entry(title: str, start: date, duration: int) -> dict[str, Any]:
    return {
        "id": None,
        "title": title,
        "start_date": start.isoformat(),
        "duration_days": duration,
        "completed": False,
    }


def _digest(
    *,
    target: str,
    as_of: str,
    resolved_title: str,
    resolved_iteration_id: str | None,
    actions: Iterable[IterationAction],
    manifest_fingerprint: str,
    snapshot_fingerprint: str,
) -> str:
    canonical = json.dumps(
        {
            "target": target,
            "as_of": as_of,
            "resolved_title": resolved_title,
            "resolved_iteration_id": resolved_iteration_id,
            "actions": [action.as_dict() for action in actions],
            "manifest_fingerprint": manifest_fingerprint,
            "snapshot_fingerprint": snapshot_fingerprint,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_iteration_plan(
    manifest: dict[str, Any],
    project_snapshot: dict[str, Any],
    *,
    target: str,
    as_of: str | date | None = None,
) -> IterationPlan:
    data, desired = _iteration_config(manifest)
    if not isinstance(target, str) or not target.strip():
        raise ManifestError("Iteration target must be a non-empty title, @current, or @next")
    target = target.strip()
    selected_date = date.today() if as_of is None else (
        as_of if isinstance(as_of, date) else _parse_date(as_of, "as_of")
    )
    field = _find_field(project_snapshot, desired["field"])
    lifecycle = discover_iterations(field, as_of=selected_date)
    configuration = field["iteration_configuration"]
    desired_duration = _positive_int(
        desired["duration_days"], "workflow.iteration.duration_days"
    )
    if configuration["duration_days"] != desired_duration:
        raise ManifestError(
            f"Project iteration duration {configuration['duration_days']} does not match "
            f"manifest duration {desired_duration}; refusing an unsafe lifecycle update"
        )

    active = configuration["iterations"]
    completed = configuration["completed_iterations"]
    completed_matches = [item for item in completed if item["title"] == target]
    if completed_matches:
        raise ManifestError(f"Iteration target '{target}' is completed")
    active_matches = [item for item in active if item["title"] == target]
    if target not in {"@current", "@next"} and active_matches:
        resolved = active_matches[0]
        actions: list[IterationAction] = []
    elif target == "@current" and lifecycle["current"] is not None:
        resolved = lifecycle["current"]
        actions = []
    elif target == "@next" and lifecycle["upcoming"]:
        resolved = lifecycle["upcoming"][0]
        actions = []
    else:
        known = sorted(
            [*active, *completed],
            key=lambda item: (item["start_date"], item["title"], item["id"]),
        )
        if not known:
            raise ManifestError(
                f"Project iteration field '{field['name']}' has no safe title/date anchor"
            )
        last = known[-1]
        last_start = _parse_date(last["start_date"], "iteration start_date")
        next_start = last_start + timedelta(days=last["duration_days"])
        current = lifecycle["current"]
        additions: list[dict[str, Any]] = []
        if current is None:
            if next_start != selected_date:
                raise ManifestError(
                    "Cannot safely extend a stale or gapped iteration schedule; "
                    "the next derived start must equal as_of"
                )
            derived_current = _new_entry(
                _increment_title(last["title"]), next_start, desired_duration
            )
            additions.append(derived_current)
            next_start += timedelta(days=desired_duration)
            last_title = derived_current["title"]
            derived_next = _new_entry(
                _increment_title(last_title), next_start, desired_duration
            )
            additions.append(derived_next)
            if target == "@current" or target == derived_current["title"]:
                resolved = derived_current
            else:
                resolved = derived_next
        else:
            derived_next = _new_entry(
                _increment_title(last["title"]), next_start, desired_duration
            )
            additions.append(derived_next)
            resolved = derived_next

        if target not in {"@current", "@next", resolved["title"]}:
            raise ManifestError(
                f"Iteration target '{target}' does not exist; the only safe derived "
                f"target is '{resolved['title']}'"
            )
        replacement = {
            "start_date": configuration["start_date"],
            "duration_days": configuration["duration_days"],
            "iterations": [*active, *additions],
            "completed_iterations": completed,
        }
        actions = [
            IterationAction(
                "project.field.update_iterations",
                {
                    "name": field["name"],
                    "field_id": field["id"],
                    "iteration_configuration": replacement,
                },
                {"field": field},
            )
        ]

    manifest_fingerprint = state_fingerprint(data)
    snapshot_fingerprint = state_fingerprint(project_snapshot)
    as_of_value = selected_date.isoformat()
    resolved_id = resolved.get("id")
    digest = _digest(
        target=target,
        as_of=as_of_value,
        resolved_title=resolved["title"],
        resolved_iteration_id=resolved_id,
        actions=actions,
        manifest_fingerprint=manifest_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
    )
    return IterationPlan(
        target=target,
        as_of=as_of_value,
        resolved_title=resolved["title"],
        resolved_iteration_id=resolved_id,
        actions=actions,
        digest=digest,
        manifest_fingerprint=manifest_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
    )


def apply_iteration_plan(
    plan: IterationPlan,
    *,
    executor: Callable[[IterationAction], Any],
    confirmation: str | None,
    manifest: dict[str, Any] | None = None,
    project_snapshot: dict[str, Any] | None = None,
    journal: Journal | None = None,
) -> ApplyReceipt:
    if not confirmation or confirmation != plan.digest:
        raise IterationAuthorizationError(
            "Iteration apply requires the exact reviewed plan digest"
        )
    if _digest(
        target=plan.target,
        as_of=plan.as_of,
        resolved_title=plan.resolved_title,
        resolved_iteration_id=plan.resolved_iteration_id,
        actions=plan.actions,
        manifest_fingerprint=plan.manifest_fingerprint,
        snapshot_fingerprint=plan.snapshot_fingerprint,
    ) != plan.digest:
        raise IterationAuthorizationError("Iteration plan changed after validation")
    if manifest is None or project_snapshot is None:
        raise IterationAuthorizationError(
            "Iteration apply requires a freshly verified manifest and Project snapshot"
        )
    fresh_plan = build_iteration_plan(
        manifest, project_snapshot, target=plan.target, as_of=plan.as_of
    )
    if fresh_plan.digest != plan.digest:
        raise IterationAuthorizationError(
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


def verify_iteration_apply(
    plan: IterationPlan,
    manifest: dict[str, Any],
    refreshed_snapshot: dict[str, Any],
) -> IterationPlan:
    """Verify convergence and server-owned identity preservation after apply."""

    verified = build_iteration_plan(
        manifest, refreshed_snapshot, target=plan.target, as_of=plan.as_of
    )
    if not verified.ready:
        raise IterationAuthorizationError(
            "Iteration update did not converge to an assignable target"
        )
    if plan.actions:
        previous_field = plan.actions[0].precondition.get("field")
        if not isinstance(previous_field, dict):
            raise IterationAuthorizationError(
                "Iteration update plan omitted the reviewed field precondition"
            )
        refreshed_field = _find_field(refreshed_snapshot, previous_field["name"])
        for list_name in ("iterations", "completed_iterations"):
            previous_entries = previous_field["iteration_configuration"][list_name]
            refreshed_entries = refreshed_field["iteration_configuration"][list_name]
            refreshed_by_title = {entry["title"]: entry for entry in refreshed_entries}
            for entry in previous_entries:
                if refreshed_by_title.get(entry["title"]) != entry:
                    raise IterationAuthorizationError(
                        f"GitHub changed or removed reviewed iteration identity "
                        f"'{entry['title']}' during the configuration update"
                    )
    if not verified.resolved_iteration_id:
        raise IterationAuthorizationError(
            "Resolved iteration has no refreshed GitHub identity; do not assign items"
        )
    return verified


def iteration_plan_from_dict(data: dict[str, Any]) -> IterationPlan:
    if not isinstance(data, dict) or not isinstance(data.get("actions"), list):
        raise ManifestError("Iteration plan must contain an actions array")
    actions: list[IterationAction] = []
    for index, raw in enumerate(data["actions"]):
        if not isinstance(raw, dict):
            raise ManifestError(f"Iteration action at index {index} must be an object")
        kind = raw.get("kind")
        payload = raw.get("payload")
        precondition = raw.get("precondition")
        if not isinstance(kind, str) or not isinstance(payload, dict) or not isinstance(precondition, dict):
            raise ManifestError(f"Iteration action at index {index} is malformed")
        actions.append(IterationAction(kind, payload, precondition))
    required = (
        "target",
        "as_of",
        "resolved_title",
        "digest",
        "manifest_fingerprint",
        "snapshot_fingerprint",
    )
    if any(not isinstance(data.get(key), str) for key in required):
        raise ManifestError("Iteration plan metadata is malformed")
    resolved_id = data.get("resolved_iteration_id")
    if resolved_id is not None and not isinstance(resolved_id, str):
        raise ManifestError("Iteration plan resolved_iteration_id is malformed")
    digest = _digest(
        target=data["target"],
        as_of=data["as_of"],
        resolved_title=data["resolved_title"],
        resolved_iteration_id=resolved_id,
        actions=actions,
        manifest_fingerprint=data["manifest_fingerprint"],
        snapshot_fingerprint=data["snapshot_fingerprint"],
    )
    if digest != data["digest"]:
        raise ManifestError("Iteration plan digest does not match its actions")
    return IterationPlan(
        target=data["target"],
        as_of=data["as_of"],
        resolved_title=data["resolved_title"],
        resolved_iteration_id=resolved_id,
        actions=actions,
        digest=digest,
        manifest_fingerprint=data["manifest_fingerprint"],
        snapshot_fingerprint=data["snapshot_fingerprint"],
    )
