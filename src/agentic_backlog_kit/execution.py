from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable


def state_fingerprint(value: Any) -> str:
    """Hash JSON state canonically while preserving semantically ordered arrays."""

    def normalize(current: Any) -> Any:
        if isinstance(current, dict):
            return {key: normalize(current[key]) for key in sorted(current)}
        if isinstance(current, list):
            return [normalize(entry) for entry in current]
        return current

    canonical = json.dumps(
        normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ApplyReceipt:
    plan_digest: str
    manifest_fingerprint: str
    snapshot_fingerprint: str
    status: str
    total_actions: int
    applied_actions: int
    completed_actions: list[dict[str, Any]]
    started_at: str
    updated_at: str
    applied_at: str | None = None
    failed_action: dict[str, Any] | None = None
    error: str | None = None
    hint: str | None = None


Journal = Callable[[ApplyReceipt], Any]


def receipt(
    plan_digest: str,
    manifest_fingerprint: str,
    snapshot_fingerprint: str,
    status: str,
    total_actions: int,
    completed_actions: list[dict[str, Any]],
    started_at: str,
    *,
    failed_action: dict[str, Any] | None = None,
    error: str | None = None,
    hint: str | None = None,
) -> ApplyReceipt:
    updated_at = datetime.now(UTC).isoformat()
    return ApplyReceipt(
        plan_digest=plan_digest,
        manifest_fingerprint=manifest_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
        status=status,
        total_actions=total_actions,
        applied_actions=len(completed_actions),
        completed_actions=list(completed_actions),
        started_at=started_at,
        updated_at=updated_at,
        applied_at=updated_at if status == "completed" else None,
        failed_action=failed_action,
        error=error,
        hint=hint,
    )

_UNAVAILABLE_TYPE_KINDS = frozenset({"issue.create", "issue.update"})


def failure_hint(kind: str, payload: dict[str, Any], error: BaseException) -> str | None:
    """Name the likely cause of a failed action in the operator's terms.

    A rejected write reaches the operator as whatever the transport said, which
    for GitHub is often nothing more than "Validation Failed".  The receipt
    already records the exact action; what it cannot do is explain it.  These
    hints cover the causes first use actually hit, and stay silent rather than
    guessing at one.
    """

    status = getattr(error, "status", None)
    message = str(getattr(error, "message", error))

    if kind in _UNAVAILABLE_TYPE_KINDS and status == 422:
        requested = payload.get("type")
        fallback = payload.get("fallback_label")
        if requested:
            hint = (
                f"GitHub rejected issue type {requested!r}. The organization "
                "most likely does not define it: check its issue types, or set "
                "github.issue_type_mode to 'labels'"
            )
            if fallback:
                hint += f" to use the {fallback!r} label instead"
            return hint + "."

    if status == 403 or "not accessible" in message.lower():
        return (
            "The token lacks permission for this write. Repository and Project "
            "writes need separate scopes; re-authenticate with 'project' scope "
            "for Project fields, views, and iterations."
        )

    if status == 404:
        return (
            "GitHub reported the target as absent. Rebuild the plan so it binds "
            "current state, then reconfirm it."
        )

    if status == 429 or "rate limit" in message.lower():
        return (
            "GitHub rate-limited this write. The completed actions are "
            "journaled; rebuild the plan and apply the remainder once the limit "
            "resets."
        )

    return None


def describe_failure(
    action: dict[str, Any], error: BaseException, hint: str | None = None
) -> str:
    """Render a failed action as one line naming what failed and on what."""

    kind = action.get("kind", "action")
    item_id = action.get("item_id") or action.get("payload", {}).get("name")
    subject = f" for {item_id!r}" if item_id else ""
    rendered = f"{kind}{subject} failed: {type(error).__name__}: {error}"
    return f"{rendered} {hint}" if hint else rendered
