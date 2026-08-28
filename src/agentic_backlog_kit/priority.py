from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Any

from .manifest import validate_manifest


@dataclass(frozen=True, slots=True)
class ScoredItem:
    id: str
    title: str
    type: str
    status: str
    maturity: str
    effort: int
    depends_on: tuple[str, ...]
    base_score: float
    priority_score: float


def _scores(data: dict[str, Any]) -> tuple[dict[str, float], dict[str, float]]:
    items = {item["id"]: item for item in data["items"]}
    done_statuses = set(data["workflow"]["done_statuses"])
    weights = data["scoring"]["weights"]
    boost_factor = data["scoring"]["dependency_boost"]

    base_scores: dict[str, float] = {}
    dependents: dict[str, list[str]] = {item_id: [] for item_id in items}
    for item_id, item in items.items():
        if item["status"] in done_statuses:
            base_scores[item_id] = 0.0
        else:
            base_scores[item_id] = (
                item["impact"] * weights["impact"]
                + item["business_value"] * weights["business_value"]
                + item["enabler_value"] * weights["enabler_value"]
                + (6 - item["effort"]) * weights["effort"]
            )
        for dependency in item["depends_on"]:
            dependents[dependency].append(item_id)

    final_scores: dict[str, float] = {}

    def final_score(item_id: str) -> float:
        if item_id not in final_scores:
            final_scores[item_id] = base_scores[item_id] + boost_factor * sum(
                final_score(dependent) for dependent in sorted(dependents[item_id])
            )
        return final_scores[item_id]

    for item_id in sorted(items):
        final_score(item_id)
    return base_scores, final_scores


def prioritize(manifest: dict[str, Any]) -> list[ScoredItem]:
    """Return a dependency-valid, deterministic priority order without mutation."""

    data = validate_manifest(manifest)
    items = {item["id"]: item for item in data["items"]}
    base_scores, final_scores = _scores(data)

    remaining_dependencies = {
        item_id: len(item["depends_on"]) for item_id, item in items.items()
    }
    dependents: dict[str, list[str]] = {item_id: [] for item_id in items}
    for item_id, item in items.items():
        for dependency in item["depends_on"]:
            dependents[dependency].append(item_id)

    queue: list[tuple[float, str]] = []
    for item_id, count in remaining_dependencies.items():
        if count == 0:
            heapq.heappush(queue, (-final_scores[item_id], item_id))

    ordered_ids: list[str] = []
    while queue:
        _, item_id = heapq.heappop(queue)
        ordered_ids.append(item_id)
        for dependent in sorted(dependents[item_id]):
            remaining_dependencies[dependent] -= 1
            if remaining_dependencies[dependent] == 0:
                heapq.heappush(queue, (-final_scores[dependent], dependent))

    return [
        ScoredItem(
            id=item_id,
            title=items[item_id]["title"],
            type=items[item_id]["type"],
            status=items[item_id]["status"],
            maturity=items[item_id]["maturity"],
            effort=items[item_id]["effort"],
            depends_on=tuple(items[item_id]["depends_on"]),
            base_score=round(base_scores[item_id], 4),
            priority_score=round(final_scores[item_id], 4),
        )
        for item_id in ordered_ids
    ]


def select_next(manifest: dict[str, Any]) -> ScoredItem | None:
    """Select the highest-ranked executable work item, or None when none is ready."""

    data = validate_manifest(manifest)
    by_id = {item["id"]: item for item in data["items"]}
    done_statuses = set(data["workflow"]["done_statuses"])
    work_item_types = set(data["workflow"]["work_item_types"])

    for scored in prioritize(data):
        item = by_id[scored.id]
        if item["type"] not in work_item_types:
            continue
        if item["status"] in done_statuses or item["status"] == "Blocked":
            continue
        if item["maturity"] != "ready":
            continue
        if any(by_id[dependency]["status"] not in done_statuses for dependency in item["depends_on"]):
            continue
        return scored
    return None

