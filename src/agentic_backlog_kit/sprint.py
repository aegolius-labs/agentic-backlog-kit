from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .manifest import ManifestError, validate_manifest
from .priority import ScoredItem, prioritize


@dataclass(frozen=True, slots=True)
class SprintPlan:
    sprint: str | None
    capacity: int
    committed_effort: int
    remaining_capacity: int
    items: list[ScoredItem]
    skipped: dict[str, str]


def sprint_plan_payload(
    plan: SprintPlan,
    *,
    skipped_limit: int | None = None,
) -> dict[str, Any]:
    """Return a JSON-ready sprint plan, optionally projecting skipped items.

    A large backlog can have thousands of skipped items while only a handful
    fit in a sprint.  The full mapping remains available by default for local
    callers; an explicit limit adds a total and truncation marker so a caller
    can keep a model-facing preview bounded without losing the reason that
    more entries exist.
    """

    if skipped_limit is not None and (
        isinstance(skipped_limit, bool)
        or not isinstance(skipped_limit, int)
        or skipped_limit < 0
    ):
        raise ManifestError("skipped_limit must be a non-negative integer")

    payload = {
        "sprint": plan.sprint,
        "capacity": plan.capacity,
        "committed_effort": plan.committed_effort,
        "remaining_capacity": plan.remaining_capacity,
        "items": [asdict(item) for item in plan.items],
        "skipped": dict(plan.skipped),
    }
    if skipped_limit is not None:
        skipped = payload["skipped"]
        payload["skipped"] = dict(list(skipped.items())[:skipped_limit])
        payload["skipped_count"] = len(skipped)
        payload["skipped_truncated"] = len(skipped) > skipped_limit
    return payload


def plan_sprint(
    manifest: dict[str, Any],
    *,
    capacity: int | None = None,
    sprint: str | None = None,
) -> SprintPlan:
    """Pack ready work deterministically while preserving prerequisite order."""

    data = validate_manifest(manifest)
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
    selected_ids: set[str] = set()
    selected: list[ScoredItem] = []
    skipped: dict[str, str] = {}
    remaining = selected_capacity

    for scored in prioritize(data):
        item = by_id[scored.id]
        if item["type"] not in work_item_types:
            continue
        if item["status"] in done_statuses:
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

    return SprintPlan(
        sprint=sprint,
        capacity=selected_capacity,
        committed_effort=selected_capacity - remaining,
        remaining_capacity=remaining,
        items=selected,
        skipped=skipped,
    )
