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
    )
