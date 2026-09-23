"""Project the backlog onto a timeline and render it as a Gantt chart.

A schedule is a *projection*, not an estimate. It converts effort points into
duration by one declared factor, places each item after the dependencies it
already declares, and reports the result. It invents no calendar information the
manifest does not carry: no velocity history, no per-person assignment, no
calendar of working days. What it does say is exactly what the dependency graph
and the effort points imply, which is what a Gantt chart of a backlog can
honestly say.

The projection is deterministic. The same manifest, start date and options
always produce the same schedule, so it can be regenerated and diffed rather
than maintained by hand.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .manifest import ManifestError, validate_manifest
from .priority import prioritize


DEFAULT_DAYS_PER_EFFORT = 2
MERMAID_STATUS = {
    "done": "done",
    "active": "active",
    "blocked": "crit",
}


@dataclass(frozen=True, slots=True)
class ScheduledItem:
    id: str
    title: str
    type: str
    status: str
    effort: int
    start: date
    end: date
    duration_days: int
    lane: int
    depends_on: tuple[str, ...]
    state: str
    section: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "status": self.status,
            "effort": self.effort,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_days": self.duration_days,
            "lane": self.lane,
            "depends_on": list(self.depends_on),
            "state": self.state,
            "section": self.section,
        }


@dataclass(frozen=True, slots=True)
class Schedule:
    items: list[ScheduledItem]
    start: date
    end: date
    days_per_effort: int
    lanes: int
    critical_path: list[str] = field(default_factory=list)
    excluded: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "days_per_effort": self.days_per_effort,
            "lanes": self.lanes,
            "item_count": len(self.items),
            "critical_path": list(self.critical_path),
            "excluded": dict(self.excluded),
            "items": [item.as_dict() for item in self.items],
        }


def _resolve_start(data: dict[str, Any], start: str | None) -> date:
    """Choose the projection's day zero, preferring what the manifest declares."""

    if start:
        try:
            return date.fromisoformat(start)
        except ValueError as exc:
            raise ManifestError(f"Schedule start must be an ISO date: {start}") from exc
    iteration = data["workflow"].get("iteration")
    if iteration and iteration.get("start_date"):
        return date.fromisoformat(iteration["start_date"])
    raise ManifestError(
        "Schedule needs a start date: pass --start, or declare "
        "workflow.iteration.start_date in the manifest"
    )


def _section(item: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    """Group a bar under its immediate parent, which is how a reader looks for it.

    Walking to the root instead would put every bar in one section named after
    the initiative, which groups nothing.
    """

    parent_id = item["parent"]
    if not parent_id:
        return "Unparented"
    return by_id[parent_id]["title"]


def build_schedule(
    manifest: dict[str, Any],
    *,
    start: str | None = None,
    days_per_effort: int = DEFAULT_DAYS_PER_EFFORT,
    lanes: int = 1,
    include_completed: bool = False,
) -> Schedule:
    """Place every schedulable item on a timeline its dependencies allow.

    `lanes` is how many items may run at once. One lane is a single worker and
    produces the honest serial projection; more lanes let independent work run
    in parallel, which shortens the chart without changing the dependency order.

    Completed work is excluded by default. It has no remaining duration, so
    including it would draw bars for time already spent and push everything
    after it, which is the opposite of what the chart is for.
    """

    data = validate_manifest(manifest)
    if days_per_effort < 1:
        raise ManifestError("days_per_effort must be a positive integer")
    if lanes < 1:
        raise ManifestError("lanes must be a positive integer")

    by_id = {item["id"]: item for item in data["items"]}
    done_statuses = set(data["workflow"]["done_statuses"])
    work_item_types = set(data["workflow"]["work_item_types"])
    origin = _resolve_start(data, start)

    # A container is excluded because its children carry the work. When it has
    # none, nothing else represents it, and excluding it would leave the largest
    # remaining items off the chart entirely - which is how a roadmap of
    # undecomposed features projects to an empty timeline.
    has_children = {item["parent"] for item in data["items"] if item["parent"]}

    excluded: dict[str, str] = {}
    schedulable: list[str] = []
    for scored in prioritize(data):
        item = by_id[scored.id]
        if item["type"] not in work_item_types and scored.id in has_children:
            excluded[scored.id] = (
                f"type '{item['type']}' groups work its children carry"
            )
            continue
        if not include_completed and item["status"] in done_statuses:
            excluded[scored.id] = f"already complete: status '{item['status']}'"
            continue
        schedulable.append(scored.id)

    # Priority order is the tie-break, but a dependency always wins, so release
    # an item only once everything it waits on is placed. Kahn's algorithm with
    # a rank-ordered heap keeps that linear in the size of the graph; rescanning
    # the remainder each round would not survive a large backlog.
    selected = set(schedulable)
    rank = {item_id: index for index, item_id in enumerate(schedulable)}
    waiting_on = {
        item_id: sum(
            1 for dependency in by_id[item_id]["depends_on"] if dependency in selected
        )
        for item_id in schedulable
    }
    dependents: dict[str, list[str]] = {item_id: [] for item_id in schedulable}
    for item_id in schedulable:
        for dependency in by_id[item_id]["depends_on"]:
            if dependency in selected:
                dependents[dependency].append(item_id)

    placed: dict[str, ScheduledItem] = {}
    lane_free = [origin] * lanes
    ready = [
        (rank[item_id], item_id) for item_id in schedulable if waiting_on[item_id] == 0
    ]
    heapq.heapify(ready)

    while ready:
        _, item_id = heapq.heappop(ready)
        item = by_id[item_id]
        duration = max(int(item["effort"]), 1) * days_per_effort
        earliest = origin
        for dependency in item["depends_on"]:
            if dependency in placed:
                earliest = max(earliest, placed[dependency].end + timedelta(days=1))
        lane = min(range(lanes), key=lambda index: (lane_free[index], index))
        begins = max(earliest, lane_free[lane])
        ends = begins + timedelta(days=duration - 1)
        lane_free[lane] = ends + timedelta(days=1)
        placed[item_id] = ScheduledItem(
            id=item_id,
            title=item["title"],
            type=item["type"],
            status=item["status"],
            effort=int(item["effort"]),
            start=begins,
            end=ends,
            duration_days=duration,
            lane=lane,
            depends_on=tuple(item["depends_on"]),
            state=_state(item, done_statuses),
            section=_section(item, by_id),
        )
        for dependent in dependents[item_id]:
            waiting_on[dependent] -= 1
            if waiting_on[dependent] == 0:
                heapq.heappush(ready, (rank[dependent], dependent))

    if len(placed) != len(schedulable):
        # validate_manifest already rejects cycles, so this is unreachable
        # unless that contract changes. Fail loudly rather than emit a chart
        # that quietly drops work.
        raise ManifestError(
            "Schedule could not place: "
            + ", ".join(sorted(set(schedulable) - set(placed)))
        )

    ordered = sorted(placed.values(), key=lambda entry: (entry.start, rank[entry.id]))
    finish = max((entry.end for entry in ordered), default=origin)
    return Schedule(
        items=ordered,
        start=origin,
        end=finish,
        days_per_effort=days_per_effort,
        lanes=lanes,
        critical_path=_critical_path(placed),
        excluded=excluded,
    )


def _state(item: dict[str, Any], done_statuses: set[str]) -> str:
    if item["status"] in done_statuses:
        return "done"
    if item["status"] == "Blocked":
        return "blocked"
    if item["status"] in {"In Progress", "In Review"}:
        return "active"
    return "planned"


def _critical_path(placed: dict[str, ScheduledItem]) -> list[str]:
    """The longest dependency chain, which is what actually sets the end date.

    Only scheduled dependencies count. A chain through work this projection
    excluded would describe a timeline the chart does not draw.
    """

    longest: dict[str, tuple[int, list[str]]] = {}

    def walk(item_id: str) -> tuple[int, list[str]]:
        if item_id in longest:
            return longest[item_id]
        entry = placed[item_id]
        best_days, best_path = 0, []
        for dependency in sorted(entry.depends_on):
            if dependency not in placed:
                continue
            days, path = walk(dependency)
            if days > best_days:
                best_days, best_path = days, path
        longest[item_id] = (best_days + entry.duration_days, [*best_path, item_id])
        return longest[item_id]

    best: tuple[int, list[str]] = (0, [])
    for item_id in sorted(placed):
        candidate = walk(item_id)
        if candidate[0] > best[0]:
            best = candidate
    return best[1]


def _mermaid_label(text: str) -> str:
    """Keep a title on one line and out of Mermaid's delimiters."""

    cleaned = " ".join(str(text).split())
    for character in (":", "#", ";", "<", ">"):
        cleaned = cleaned.replace(character, " ")
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > 60:
        cleaned = cleaned[:57].rstrip() + "..."
    return cleaned or "Untitled"


def render_mermaid(schedule: Schedule, *, title: str = "Backlog projection") -> str:
    """Render the schedule as a Mermaid `gantt` block.

    Mermaid is text, renders natively on GitHub and in most Markdown viewers,
    and adds no dependency - which is the only kind of chart this kit can ship
    while staying on the standard library.
    """

    lines = [
        "```mermaid",
        "gantt",
        f"    title {_mermaid_label(title)}",
        "    dateFormat YYYY-MM-DD",
        "    axisFormat %b %d",
        "",
    ]
    # Group by section rather than following the timeline, so a section appears
    # once. Sections keep the order in which their work first starts, and the
    # bars inside one stay in start order.
    order: dict[str, int] = {}
    grouped: dict[str, list[ScheduledItem]] = {}
    for index, item in enumerate(schedule.items):
        order.setdefault(item.section, index)
        grouped.setdefault(item.section, []).append(item)

    for section in sorted(grouped, key=lambda name: order[name]):
        lines.append(f"    section {_mermaid_label(section)}")
        for item in grouped[section]:
            tag = MERMAID_STATUS.get(item.state)
            fields = [
                part
                for part in (
                    tag,
                    item.id,
                    item.start.isoformat(),
                    f"{item.duration_days}d",
                )
                if part
            ]
            lines.append(f"    {_mermaid_label(item.title)} :{', '.join(fields)}")
    lines.append("```")
    return "\n".join(lines)


def render_markdown(
    schedule: Schedule, *, title: str = "Backlog projection", command: str | None = None
) -> str:
    """Render a self-describing document: the chart, its basis, and its limits.

    A Gantt chart read without its assumptions is a promise about dates. Stating
    the conversion factor, the lane count and what was left out on the same page
    is what keeps it a projection.
    """

    critical = " -> ".join(schedule.critical_path) or "none"
    lines = [
        f"# {title}",
        "",
        "**Generated. Do not edit by hand.**"
        + (f" Regenerate with `{command}`." if command else ""),
        "",
        f"- Projection start: `{schedule.start.isoformat()}`",
        f"- Projected finish: `{schedule.end.isoformat()}`",
        f"- Scheduled items: {len(schedule.items)}",
        f"- Duration basis: {schedule.days_per_effort} day(s) per effort point",
        f"- Parallel lanes: {schedule.lanes}",
        f"- Critical path: `{critical}`",
        "",
        "This is a **projection, not an estimate**. Durations come from effort",
        "points multiplied by one declared factor, and order comes from the",
        "dependencies the backlog already declares. There is no velocity history,",
        "no assignment, and no calendar of working days behind these dates.",
        "",
        render_mermaid(schedule, title=title),
    ]
    if schedule.excluded:
        lines += [
            "",
            "## Not scheduled",
            "",
            "| Item | Why |",
            "| --- | --- |",
        ]
        for item_id in sorted(schedule.excluded):
            lines.append(f"| `{item_id}` | {schedule.excluded[item_id]} |")
    return "\n".join(lines) + "\n"
