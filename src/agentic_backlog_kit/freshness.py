"""Fresh-by-default operational state resolution (owner decision D1, R35/S-R35-1).

GitHub owns `Status` and the iteration field for work it already tracks; the
manifest owns intent and is never written with observations (`docs/operational-authority.md`).
Before this module, planning commands (`next`, `prioritize`, `sprint-plan`,
`gantt`) read local intent unless an operator remembered to pass
`--operational-snapshot`, which meant stale answers by default across
sessions, machines, and users.

The owner's decision: fresh by default, offline explicit. This module
resolves which observed snapshot (if any) a planning command should compose
onto the manifest, following this order:

1. An explicit `--operational-snapshot PATH` is used exactly as given.
2. `--offline` uses local intent only; no snapshot is read.
3. Otherwise (the new default), a small on-disk cache is used if it is still
   young enough and targets the same GitHub owner/repository/project as the
   manifest; otherwise a fresh snapshot is read and the cache is refreshed.
   A failure while fetching fresh state fails closed - it never silently
   falls back to local intent.

The cache is a thin wrapper around a snapshot exactly as `_read_snapshot`
returns it (see `write_cache`): it never mutates the snapshot's own content,
because snapshot content feeds plan fingerprints elsewhere in the kit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

CACHE_VERSION = 1
DEFAULT_CACHE_PATH = Path(".agentic-backlog/cache/observed-snapshot.json")
DEFAULT_MAX_AGE_SECONDS = 300

_ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class FreshnessError(RuntimeError):
    """Raised when the requested operational state cannot be resolved safely.

    This covers both operator input errors (conflicting flags) and a failed
    auto-fetch: the kit fails closed rather than silently answering from
    stale local intent.
    """


def utc_now_iso(*, now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime(_ISO_FORMAT)


def _parse_iso(value: str) -> datetime:
    return datetime.strptime(value, _ISO_FORMAT).replace(tzinfo=timezone.utc)


def cache_target(manifest: dict[str, Any]) -> dict[str, Any]:
    github = manifest["github"]
    return {
        "owner": github["owner"],
        "repository": github["repository"],
        "project_number": github["project_number"],
    }


def read_cache(cache_path: Path) -> dict[str, Any] | None:
    """Return the cache wrapper, or None when it is absent or unreadable."""

    try:
        raw = cache_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("cache_version") != CACHE_VERSION:
        return None
    if not isinstance(data.get("snapshot"), dict) or not isinstance(
        data.get("target"), dict
    ):
        return None
    return data


def cache_is_fresh(
    cache: dict[str, Any] | None,
    manifest: dict[str, Any],
    max_age_seconds: int,
    *,
    now: datetime | None = None,
) -> bool:
    if cache is None:
        return False
    if cache.get("target") != cache_target(manifest):
        return False
    observed_at = cache.get("observed_at")
    if not isinstance(observed_at, str):
        return False
    try:
        observed = _parse_iso(observed_at)
    except ValueError:
        return False
    current = now or datetime.now(timezone.utc)
    age = (current - observed).total_seconds()
    return 0 <= age <= max_age_seconds


def write_cache(
    cache_path: Path,
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Write the cache wrapper atomically. Never mutates `snapshot` itself."""

    cache = {
        "cache_version": CACHE_VERSION,
        "observed_at": observed_at or utc_now_iso(),
        "target": cache_target(manifest),
        "snapshot": snapshot,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(cache_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary.replace(cache_path)
    return cache


def invalidate_cache(cache_path: Path = DEFAULT_CACHE_PATH) -> None:
    """Delete the cache, if present, so the next planning command refetches.

    Every write path that changes GitHub must call this after a successful
    apply: the cache would otherwise keep answering with the state from
    before the write until it aged out on its own.
    """

    try:
        cache_path.unlink()
    except FileNotFoundError:
        pass


def manifest_behind(
    manifest: dict[str, Any], snapshot: dict[str, Any]
) -> dict[str, Any] | None:
    """Detect issues the snapshot carries a kit marker for that the manifest lacks.

    This is the signature of another machine or user having added items to
    GitHub that this manifest has not yet absorbed (a stale local checkout,
    or someone else's `import-apply`/`sync-apply`). Returns None when nothing
    is unknown, so callers can omit the key entirely rather than emit an
    empty report.
    """

    manifest_ids = {entry["id"] for entry in manifest.get("items", [])}
    unknown = [
        {"item_id": issue["abk_id"], "number": issue["number"]}
        for issue in snapshot.get("issues", [])
        if isinstance(issue, dict) and issue.get("abk_id") not in (None, "")
        and issue["abk_id"] not in manifest_ids
    ]
    if not unknown:
        return None
    unknown.sort(key=lambda entry: str(entry["item_id"]))
    return {
        "unknown_managed_issues": unknown,
        "hint": (
            "Another machine or user may have added items GitHub already "
            "tracks. Run `git pull` to pick up a newer manifest, or "
            "`abk import-reconcile` to recover them here."
        ),
    }


@dataclass(frozen=True, slots=True)
class SnapshotResolution:
    """The snapshot (if any) to use, and how it was obtained."""

    snapshot: dict[str, Any] | None
    freshness: dict[str, Any]


def resolve_snapshot(
    manifest: dict[str, Any],
    *,
    snapshot_path: str | None,
    offline: bool,
    max_age_seconds: int,
    fetch_snapshot: Callable[[], dict[str, Any]],
    cache_path: Path = DEFAULT_CACHE_PATH,
    now: datetime | None = None,
) -> SnapshotResolution:
    """Resolve the observed-state snapshot a planning or evidence command uses.

    `snapshot` is None exactly when the caller should use local intent alone
    (`--offline` with no explicit snapshot). `fetch_snapshot` is called only
    when the cache is missing, stale, or targets a different owner/repository
    /project than the manifest declares; its failures are wrapped in
    `FreshnessError` so the caller fails closed instead of falling back to
    stale state silently.
    """

    if snapshot_path and offline:
        raise FreshnessError(
            "--offline and --operational-snapshot cannot be used together: "
            "pass at most one."
        )

    if snapshot_path:
        snapshot = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
        return SnapshotResolution(snapshot, {"source": "explicit"})

    if offline:
        return SnapshotResolution(None, {"source": "offline"})

    current = now or datetime.now(timezone.utc)
    cache = read_cache(cache_path)
    if cache_is_fresh(cache, manifest, max_age_seconds, now=current):
        observed_at = cache["observed_at"]
        snapshot = cache["snapshot"]
        source = "cache"
    else:
        try:
            snapshot = fetch_snapshot()
        except RuntimeError as error:
            # GitHubApiError, missing-auth RuntimeError from the transport
            # factory, and similar transport failures are all RuntimeError
            # subclasses or plain RuntimeErrors in this codebase.
            raise FreshnessError(
                "Could not read fresh operational state from GitHub: "
                f"{error} Pass --offline for a local-intent preview instead."
            ) from error
        except OSError as error:
            raise FreshnessError(
                "Could not read fresh operational state from GitHub: "
                f"{error} Pass --offline for a local-intent preview instead."
            ) from error
        observed_at = utc_now_iso(now=current)
        write_cache(cache_path, manifest, snapshot, observed_at=observed_at)
        source = "fetched"

    age_seconds = max(0, int((current - _parse_iso(observed_at)).total_seconds()))
    freshness = {
        "source": source,
        "observed_at": observed_at,
        "age_seconds": age_seconds,
    }
    return SnapshotResolution(snapshot, freshness)
