from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .iterations import IterationPlan, build_iteration_plan
from .manifest import ManifestError, validate_manifest
from .priority import ScoredItem, prioritize


@dataclass(frozen=True, slots=True)
class SprintPlan:
    sprint: str | None
    iteration_id: str | None
    iteration_plan: IterationPlan | None
    capacity: int
    committed_effort: int
    remaining_capacity: int
    items: list[ScoredItem]
    skipped: dict[str, str]
    retained: list[ScoredItem] = field(default_factory=list)
    retained_effort: int = 0
    overage: int = 0
    carryover_available: dict[str, str] = field(default_factory=dict)
    carryover_selected: list[str] = field(default_factory=list)

    @property
    def ready_to_commit(self) -> bool:
        return (
            self.sprint is not None
            and self.iteration_plan is not None
            and self.iteration_plan.ready
        )


def _retained_entry(item: ScoredItem) -> dict[str, Any]:
    """Project work already committed to this sprint compactly.

    Retained work is context, not the decision: the caller needs to know what
    occupies the sprint and what it costs, while the ranking detail that
    justifies a *new* selection adds bytes without adding an answer.
    """

    return {
        "id": item.id,
        "title": item.title,
        "type": item.type,
        "status": item.status,
        "effort": item.effort,
    }


def sprint_plan_payload(
    plan: SprintPlan,
    *,
    skipped_limit: int | None = None,
) -> dict[str, Any]:
    """Return a JSON-ready sprint plan, optionally projecting skipped items.

    A large backlog can have thousands of skipped, retained, or
    committed-elsewhere items while only a handful fit in a sprint.  The full
    mappings remain available by default for local callers; an explicit limit
    projects each of them and adds a total and truncation marker, so a caller
    can keep a model-facing preview bounded without losing the fact that more
    entries exist.
    """

    if skipped_limit is not None and (
        isinstance(skipped_limit, bool)
        or not isinstance(skipped_limit, int)
        or skipped_limit < 0
    ):
        raise ManifestError("skipped_limit must be a non-negative integer")

    payload = {
        "sprint": plan.sprint,
        "iteration_id": plan.iteration_id,
        "ready_to_commit": plan.ready_to_commit,
        "iteration_plan": (
            plan.iteration_plan.as_dict() if plan.iteration_plan is not None else None
        ),
        "capacity": plan.capacity,
        "committed_effort": plan.committed_effort,
        "remaining_capacity": plan.remaining_capacity,
        "items": [asdict(item) for item in plan.items],
        "retained": [_retained_entry(item) for item in plan.retained],
        "retained_effort": plan.retained_effort,
        "overage": plan.overage,
        "carryover_available": dict(plan.carryover_available),
        "carryover_selected": list(plan.carryover_selected),
        "skipped": dict(plan.skipped),
    }
    if skipped_limit is not None:
        # Every list that grows with the backlog is projected, not just the
        # skipped one: on a large backlog the work committed elsewhere and the
        # work already in this sprint are each far longer than the decision.
        for name in ("skipped", "carryover_available"):
            full = payload[name]
            payload[name] = dict(list(full.items())[:skipped_limit])
            payload[f"{name}_count"] = len(full)
            payload[f"{name}_truncated"] = len(full) > skipped_limit
        retained = payload["retained"]
        payload["retained"] = retained[:skipped_limit]
        payload["retained_count"] = len(retained)
        payload["retained_truncated"] = len(retained) > skipped_limit
    return payload


def _normalize_carryover(
    carryover: set[str] | frozenset[str] | None,
    by_id: dict[str, dict[str, Any]],
    done_statuses: set[str],
    sprint: str | None,
) -> frozenset[str]:
    """Check every requested carryover before any capacity is committed."""

    if not carryover:
        return frozenset()
    if sprint is None:
        raise ManifestError(
            "Carryover review requires a target sprint; without one nothing is "
            "withheld from selection"
        )
    for item_id in sorted(carryover):
        item = by_id.get(item_id)
        if item is None:
            raise ManifestError(f"Carryover references unknown item '{item_id}'")
        if item["status"] in done_statuses:
            raise ManifestError(
                f"Carryover item '{item_id}' is already complete"
            )
        assigned = item.get("sprint")
        if not assigned:
            raise ManifestError(
                f"Carryover item '{item_id}' is not committed to a sprint; "
                "it is already available for selection"
            )
        if sprint is not None and assigned == sprint:
            raise ManifestError(
                f"Carryover item '{item_id}' is already committed to '{sprint}'"
            )
    return frozenset(carryover)


def plan_sprint(
    manifest: dict[str, Any],
    *,
    capacity: int | None = None,
    sprint: str | None = None,
    project_snapshot: dict[str, Any] | None = None,
    as_of: str | None = None,
    carryover: set[str] | frozenset[str] | None = None,
) -> SprintPlan:
    """Pack ready work deterministically while preserving prerequisite order.

    Replanning never moves committed work on its own (policy A).  Work already
    assigned to the target sprint is *retained*: it consumes capacity once and
    is reported separately rather than re-selected.  Work assigned to a
    different sprint is withheld from automatic selection and offered as
    carryover, because quietly pulling it here would silently break somebody
    else's commitment.  Naming an id in ``carryover`` is the explicit review
    that lets it move.
    """

    data = validate_manifest(manifest)
    iteration_plan: IterationPlan | None = None
    iteration_id: str | None = None
    if sprint is not None:
        if project_snapshot is None:
            raise ManifestError(
                "A sprint target requires a fresh Project scaffold snapshot"
            )
        iteration_plan = build_iteration_plan(
            data, project_snapshot, target=sprint, as_of=as_of
        )
        sprint = iteration_plan.resolved_title
        iteration_id = iteration_plan.resolved_iteration_id
    selected_capacity = (
        data["workflow"]["default_capacity"] if capacity is None else capacity
    )
    if (
        isinstance(selected_capacity, bool)
        or not isinstance(selected_capacity, int)
        or selected_capacity < 1
    ):
        raise ManifestError("Sprint capacity must be a positive integer")

    by_id = {item["id"]: item for item in data["items"]}
    done_statuses = set(data["workflow"]["done_statuses"])
    work_item_types = set(data["workflow"]["work_item_types"])
    completed = {
        item_id for item_id, item in by_id.items() if item["status"] in done_statuses
    }
    ordered = prioritize(data)
    requested_carryover = _normalize_carryover(carryover, by_id, done_statuses, sprint)

    retained: list[ScoredItem] = []
    retained_ids: set[str] = set()
    retained_effort = 0
    carryover_available: dict[str, str] = {}
    carryover_selected: list[str] = []

    # Commitment is relative to a target. Without one there is no sprint to
    # protect and no "elsewhere" to withhold from, so an untargeted preview
    # ranks the whole backlog exactly as it did before policy A.
    if sprint is not None:
        for scored in ordered:
            item = by_id[scored.id]
            if item["type"] not in work_item_types or item["status"] in done_statuses:
                continue
            assigned = item.get("sprint")
            if not assigned:
                continue
            if assigned == sprint:
                # Already committed here. Count it once; do not re-select it,
                # and do not drop it because its status has moved on.
                retained.append(scored)
                retained_ids.add(scored.id)
                retained_effort += item["effort"]
            elif scored.id not in requested_carryover:
                carryover_available[scored.id] = assigned

    selected_ids: set[str] = set(retained_ids)
    selected: list[ScoredItem] = []
    skipped: dict[str, str] = {}
    remaining = selected_capacity - retained_effort
    overage = max(0, retained_effort - selected_capacity)

    for scored in ordered:
        item = by_id[scored.id]
        if item["type"] not in work_item_types:
            continue
        if item["status"] in done_statuses:
            continue
        if scored.id in retained_ids:
            continue
        if scored.id in carryover_available:
            # Reported once, in carryover_available, with the sprint that holds
            # it. Repeating it in skipped would double a list that grows with
            # the backlog.
            continue
        if item["status"] == "Blocked":
            skipped[scored.id] = "status is Blocked"
            continue
        if item["maturity"] != "ready":
            skipped[scored.id] = f"maturity is {item['maturity']}"
            continue
        unavailable = [
            dependency
            for dependency in item["depends_on"]
            if dependency not in completed and dependency not in selected_ids
        ]
        if unavailable:
            skipped[scored.id] = f"unmet dependencies: {', '.join(unavailable)}"
            continue
        if item["effort"] > remaining:
            skipped[scored.id] = (
                f"effort {item['effort']} exceeds remaining capacity {remaining}"
            )
            continue
        selected.append(scored)
        selected_ids.add(scored.id)
        remaining -= item["effort"]
        if scored.id in requested_carryover:
            carryover_selected.append(scored.id)

    return SprintPlan(
        sprint=sprint,
        iteration_id=iteration_id,
        iteration_plan=iteration_plan,
        capacity=selected_capacity,
        committed_effort=selected_capacity - remaining,
        remaining_capacity=remaining,
        items=selected,
        skipped=skipped,
        retained=retained,
        retained_effort=retained_effort,
        overage=overage,
        carryover_available=carryover_available,
        carryover_selected=carryover_selected,
    )
