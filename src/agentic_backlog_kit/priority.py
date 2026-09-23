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
    """Return base and dependency-boosted final scores without recursive traversal.

    Completed work scores zero and never propagates a boost, so a finished
    prerequisite cannot outrank or inflate the work that still remains.
    """

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

    # A final score consumes the final scores of everything that depends on it,
    # so resolve items in dependent-first order. The manifest is already proven
    # acyclic, so every item is released exactly once.
    pending = {item_id: len(dependents[item_id]) for item_id in items}
    ready = [item_id for item_id in sorted(items) if pending[item_id] == 0]

    final_scores: dict[str, float] = {}
    while ready:
        item_id = ready.pop()
        if items[item_id]["status"] in done_statuses:
            final_scores[item_id] = 0.0
        else:
            final_scores[item_id] = base_scores[item_id] + boost_factor * sum(
                final_scores[dependent] for dependent in sorted(dependents[item_id])
            )
        for prerequisite in sorted(items[item_id]["depends_on"]):
            pending[prerequisite] -= 1
            if pending[prerequisite] == 0:
                ready.append(prerequisite)

    if len(final_scores) != len(items):  # pragma: no cover - guarded by validation
        unresolved = sorted(set(items) - set(final_scores))
        raise ValueError(f"Unresolved dependency graph for items: {unresolved}")

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

    done_statuses = set(data["workflow"]["done_statuses"])

    def rank(item_id: str) -> tuple[int, float, str]:
        """Order the release queue, completed work first.

        Completed work scores zero, so ranking it by score alone would release
        it last and hold back everything that depends on it - which is the
        opposite of the truth, because finished work blocks nothing.  Releasing
        it first keeps the order dependency-valid and lets the work that is
        genuinely next surface at the front.
        """

        is_open = 0 if items[item_id]["status"] in done_statuses else 1
        return (is_open, -final_scores[item_id], item_id)

    queue: list[tuple[int, float, str]] = []
    for item_id, count in remaining_dependencies.items():
        if count == 0:
            heapq.heappush(queue, rank(item_id))

    ordered_ids: list[str] = []
    while queue:
        _, _, item_id = heapq.heappop(queue)
        ordered_ids.append(item_id)
        for dependent in sorted(dependents[item_id]):
            remaining_dependencies[dependent] -= 1
            if remaining_dependencies[dependent] == 0:
                heapq.heappush(queue, rank(dependent))

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


def _not_executable(
    item: dict[str, Any],
    *,
    by_id: dict[str, dict[str, Any]],
    done_statuses: set[str],
    work_item_types: set[str],
) -> str | None:
    """Return why this item cannot be worked next, or None when it can.

    Selection used to drop each of these silently, which left the honest
    answer - what the backlog would have handed you, and what stands in the
    way - unavailable to anyone who had not read the engine.
    """

    if item["type"] not in work_item_types:
        return (
            f"type '{item['type']}' is a container, not work; "
            "its children carry the work"
        )
    if item["status"] in done_statuses:
        return f"already complete: status '{item['status']}'"
    if item["status"] == "Blocked":
        return "explicitly blocked; unblock it before it can be selected"
    if item["maturity"] != "ready":
        return (
            f"not refined: maturity is '{item['maturity']}'. Refine it with "
            "item-update before it can be selected"
        )
    waiting = sorted(
        dependency
        for dependency in item["depends_on"]
        if by_id[dependency]["status"] not in done_statuses
    )
    if waiting:
        return "waiting on " + ", ".join(waiting)
    return None


def explain_next(
    manifest: dict[str, Any], *, limit: int = 5
) -> tuple[ScoredItem | None, list[dict[str, Any]]]:
    """Select the next executable item, and say what outranked it and why.

    A ranking that reports one id and silently discards everything above it
    cannot be picked up by anyone who was not present when it was produced.
    `passed_over` names the higher-scoring items that were not selected, in
    rank order, each with the reason, so the next agent sees the same backlog
    the engine saw.
    """

    data = validate_manifest(manifest)
    by_id = {item["id"]: item for item in data["items"]}
    done_statuses = set(data["workflow"]["done_statuses"])
    work_item_types = set(data["workflow"]["work_item_types"])

    def blocked_because(item_id: str) -> str | None:
        return _not_executable(
            by_id[item_id],
            by_id=by_id,
            done_statuses=done_statuses,
            work_item_types=work_item_types,
        )

    ranked = prioritize(data)
    best: ScoredItem | None = None
    for scored in ranked:
        # Take the highest-scoring executable item rather than the first one
        # the dependency order happens to reach; ties keep that order.
        if blocked_because(scored.id) is None and (
            best is None or scored.priority_score > best.priority_score
        ):
            best = scored

    passed_over: list[dict[str, Any]] = []
    if limit > 0:
        threshold = best.priority_score if best else None
        for scored in sorted(
            ranked, key=lambda entry: (-entry.priority_score, entry.id)
        ):
            if threshold is not None and scored.priority_score <= threshold:
                break
            if by_id[scored.id]["status"] in done_statuses:
                # Completed work already scores zero. Naming it here would bury
                # the reasons that actually stand between an operator and the
                # work under reasons that are only bookkeeping.
                continue
            reason = blocked_because(scored.id)
            if reason is None:
                continue
            passed_over.append(
                {
                    "id": scored.id,
                    "title": scored.title,
                    "priority_score": scored.priority_score,
                    "reason": reason,
                }
            )
            if len(passed_over) >= limit:
                break
    return best, passed_over


def select_next(manifest: dict[str, Any]) -> ScoredItem | None:
    """Select the highest-ranked executable work item, or None when none is ready."""

    return explain_next(manifest, limit=0)[0]
