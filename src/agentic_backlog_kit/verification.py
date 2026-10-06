"""Post-apply verification that tells GitHub's read-after-write lag from drift.

After a sync apply, a fresh read and re-plan should find nothing left to do.
GitHub's reads are eventually consistent, though, so a read moments after a
write can still show the old state and re-propose exactly what was just
written. Reporting that as drift sends the operator chasing a problem that
resolves itself a few seconds later.

So a residual action that asks again for values the apply just wrote, on the
same item, is re-read within a bounded window before it is called drift. A residual the apply did not
write is drift at once: lag can only delay what was written, never invent new
work. Whatever outcome, the result records whether lag was observed and how
long convergence took, so the receipt carries the evidence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .sync import SyncAction, SyncPlan, build_sync_plan

# Seconds. Long enough to absorb the propagation delays seen on issue and field
# writes, short enough that a real drift is reported while the operator waits.
DEFAULT_VERIFY_WINDOW = 60.0
_FIRST_DELAY = 2.0

# A write can surface in a later read as a different action on the same item:
# a created issue whose body has not propagated re-plans as an update, and an
# added Project item whose fields lag re-plans as a field write.
_KIND_GROUPS = {
    "issue.create": "issue",
    "issue.update": "issue",
    "project.add_item": "project",
    "project.set_fields": "project",
    "project.transition": "project",
}


def _write_key(action: SyncAction) -> tuple[str, ...]:
    group = _KIND_GROUPS.get(action.kind, action.kind)
    if action.kind == "issue.set_parent":
        return (group, action.item_id, str(action.payload.get("parent")))
    if action.kind == "issue.add_dependency":
        return (group, action.item_id, str(action.payload.get("depends_on")))
    return (group, action.item_id)


def _written_values(action: SyncAction) -> dict[tuple[str, ...], Any]:
    if action.kind in {"project.add_item", "project.set_fields", "project.transition"}:
        fields = action.payload.get("fields") or {}
        return {("field", name): value for name, value in fields.items()}
    return {
        ("payload", key): value
        for key, value in action.payload.items()
        if not isinstance(value, (dict, list))
    }


def _is_lag(action: SyncAction, written: dict[tuple[str, ...], dict]) -> bool:
    """A residual is lag only if it asks for exactly values the apply wrote."""

    values = written.get(_write_key(action))
    if values is None:
        return False
    return all(
        key in values and values[key] == value
        for key, value in _written_values(action).items()
    )


def verify_delays(window: float) -> list[float]:
    """Return the waits before each re-read: doubling from 2s, summing to ``window``."""

    if window < 0:
        raise ValueError("The verification window cannot be negative")
    delays: list[float] = []
    remaining = float(window)
    delay = _FIRST_DELAY
    while remaining > 0:
        step = min(delay, remaining)
        delays.append(step)
        remaining -= step
        delay *= 2
    return delays


@dataclass(frozen=True, slots=True)
class SyncVerification:
    status: str
    lag_observed: bool
    reads: int
    elapsed_seconds: float
    convergence_seconds: float | None
    window_seconds: float
    lagging_actions: list[dict[str, Any]] = field(default_factory=list)
    drift_actions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def converged(self) -> bool:
        return self.status == "converged"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "lag_observed": self.lag_observed,
            "reads": self.reads,
            "elapsed_seconds": self.elapsed_seconds,
            "convergence_seconds": self.convergence_seconds,
            "window_seconds": self.window_seconds,
            "lagging_actions": list(self.lagging_actions),
            "drift_actions": list(self.drift_actions),
        }


def verify_sync_apply(
    plan: SyncPlan,
    manifest: dict[str, Any],
    read_snapshot: Callable[[], dict[str, Any]],
    *,
    applied: Iterable[SyncAction] | None = None,
    window: float = DEFAULT_VERIFY_WINDOW,
    sleep: Callable[[float], Any] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> SyncVerification:
    """Re-read and re-plan until nothing remains, lag runs out, or drift appears.

    ``applied`` defaults to every action in ``plan``; pass the completed actions
    when only part of a plan ran.
    """

    written: dict[tuple[str, ...], dict[tuple[str, ...], Any]] = {}
    for action in plan.actions if applied is None else applied:
        written.setdefault(_write_key(action), {}).update(_written_values(action))
    delays = verify_delays(window)
    started = clock()
    reads = 0
    lag_observed = False
    while True:
        snapshot = read_snapshot()
        reads += 1
        residual = build_sync_plan(
            manifest,
            snapshot,
            manage_body=plan.manage_body,
            transitions=plan.transitions,
            overwrite_remote_edits=plan.overwrite_remote_edits,
        ).actions
        lagging = [action for action in residual if _is_lag(action, written)]
        drift = [action for action in residual if not _is_lag(action, written)]
        elapsed = round(clock() - started, 3)
        if not residual:
            return SyncVerification(
                status="converged",
                lag_observed=lag_observed,
                reads=reads,
                elapsed_seconds=elapsed,
                convergence_seconds=elapsed,
                window_seconds=float(window),
            )
        if lagging:
            lag_observed = True
        if drift or not delays:
            # Lag never invents work, so an unwritten residual is drift now,
            # and the written ones still pending are left unjudged. A written
            # residual that outlasts the window is drift too.
            return SyncVerification(
                status="drift",
                lag_observed=lag_observed,
                reads=reads,
                elapsed_seconds=elapsed,
                convergence_seconds=None,
                window_seconds=float(window),
                lagging_actions=[action.as_dict() for action in lagging] if drift else [],
                drift_actions=[action.as_dict() for action in (drift or lagging)],
            )
        sleep(delays.pop(0))


__all__ = [
    "DEFAULT_VERIFY_WINDOW",
    "SyncVerification",
    "verify_delays",
    "verify_sync_apply",
]
