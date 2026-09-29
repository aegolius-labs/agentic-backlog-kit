"""S-R35-1: planning is fresh by default (owner decision D1).

Unit tests for `agentic_backlog_kit.freshness`, which resolves whether a
planning command reads an explicit snapshot, local intent (`--offline`), or
an auto-refreshed cache of GitHub's observed state.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from agentic_backlog_kit.freshness import (
    DEFAULT_MAX_AGE_SECONDS,
    FreshnessError,
    cache_is_fresh,
    cache_target,
    invalidate_cache,
    manifest_behind,
    read_cache,
    resolve_snapshot,
    utc_now_iso,
    write_cache,
)

from tests.helpers import item, manifest


def _snapshot(*issues: dict) -> dict:
    return {"schema_version": 1, "issues": list(issues)}


def _issue(abk_id: str, number: int, **fields) -> dict:
    return {"abk_id": abk_id, "number": number, **fields}


class CacheWrapperTests(unittest.TestCase):
    def test_cache_wraps_the_snapshot_without_touching_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "observed-snapshot.json"
            data = manifest(item("T-1"))
            snapshot = _snapshot(_issue("T-1", 1))

            written = write_cache(cache_path, data, snapshot)

            self.assertEqual(1, written["cache_version"])
            self.assertEqual(cache_target(data), written["target"])
            self.assertEqual(snapshot, written["snapshot"])
            # The wrapper carries the timestamp; the snapshot payload itself
            # must be byte-identical to what was passed in, since snapshot
            # content feeds plan fingerprints elsewhere.
            self.assertEqual(list(snapshot.keys()), list(written["snapshot"].keys()))

    def test_round_trips_through_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "observed-snapshot.json"
            data = manifest(item("T-1"))
            snapshot = _snapshot(_issue("T-1", 1))
            write_cache(cache_path, data, snapshot)

            reloaded = read_cache(cache_path)

            self.assertIsNotNone(reloaded)
            self.assertEqual(snapshot, reloaded["snapshot"])

    def test_missing_cache_reads_as_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "missing.json"
            self.assertIsNone(read_cache(cache_path))

    def test_invalidate_is_safe_when_the_cache_never_existed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "missing.json"
            invalidate_cache(cache_path)  # must not raise

    def test_invalidate_deletes_an_existing_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "observed-snapshot.json"
            write_cache(cache_path, manifest(item("T-1")), _snapshot())
            self.assertTrue(cache_path.exists())

            invalidate_cache(cache_path)

            self.assertFalse(cache_path.exists())


class CacheWriteSafetyTests(unittest.TestCase):
    def test_a_write_leaves_no_temporary_file_behind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "observed-snapshot.json"
            write_cache(cache_path, manifest(item("T-1")), _snapshot())
            write_cache(cache_path, manifest(item("T-1")), _snapshot())

            self.assertEqual(
                ["observed-snapshot.json"],
                sorted(entry.name for entry in Path(directory).iterdir()),
            )

    def test_a_cache_that_cannot_be_written_does_not_fail_a_fresh_read(self) -> None:
        snapshot = _snapshot(_issue("T-1", 1))
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "observed-snapshot.json"
            with patch(
                "agentic_backlog_kit.freshness.os.replace",
                side_effect=PermissionError("[WinError 5] Access is denied"),
            ):
                resolution = resolve_snapshot(
                    manifest(item("T-1")),
                    snapshot_path=None,
                    offline=False,
                    max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
                    fetch_snapshot=lambda: snapshot,
                    cache_path=cache_path,
                )

            self.assertEqual(snapshot, resolution.snapshot)
            self.assertEqual("fetched", resolution.freshness["source"])
            self.assertIn("PermissionError", resolution.freshness["cache_not_written"])
            self.assertEqual([], list(Path(directory).iterdir()))


class CacheFreshnessTests(unittest.TestCase):
    def test_fresh_within_max_age(self) -> None:
        data = manifest(item("T-1"))
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cache = {
            "cache_version": 1,
            "observed_at": utc_now_iso(now=now - timedelta(seconds=10)),
            "target": cache_target(data),
            "snapshot": _snapshot(),
        }
        self.assertTrue(cache_is_fresh(cache, data, 300, now=now))

    def test_stale_past_max_age(self) -> None:
        data = manifest(item("T-1"))
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cache = {
            "cache_version": 1,
            "observed_at": utc_now_iso(now=now - timedelta(seconds=301)),
            "target": cache_target(data),
            "snapshot": _snapshot(),
        }
        self.assertFalse(cache_is_fresh(cache, data, 300, now=now))

    def test_target_mismatch_is_never_fresh(self) -> None:
        data = manifest(item("T-1"))
        other = manifest(item("T-1"))
        other["github"]["repository"] = "elsewhere"
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cache = {
            "cache_version": 1,
            "observed_at": utc_now_iso(now=now),
            "target": cache_target(other),
            "snapshot": _snapshot(),
        }
        self.assertFalse(cache_is_fresh(cache, data, 300, now=now))

    def test_missing_cache_is_never_fresh(self) -> None:
        data = manifest(item("T-1"))
        self.assertFalse(cache_is_fresh(None, data, 300))


class ResolveSnapshotTests(unittest.TestCase):
    def test_explicit_snapshot_path_is_used_exactly_as_given(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            snapshot = _snapshot(_issue("T-1", 1))
            path.write_text(json.dumps(snapshot), encoding="utf-8")

            def fetch():
                raise AssertionError("must not fetch when an explicit path is given")

            resolution = resolve_snapshot(
                manifest(item("T-1")),
                snapshot_path=str(path),
                offline=False,
                max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
                fetch_snapshot=fetch,
            )

            self.assertEqual(snapshot, resolution.snapshot)
            self.assertEqual({"source": "explicit"}, resolution.freshness)

    def test_offline_returns_no_snapshot_and_never_fetches(self) -> None:
        def fetch():
            raise AssertionError("must not fetch when --offline is given")

        resolution = resolve_snapshot(
            manifest(item("T-1")),
            snapshot_path=None,
            offline=True,
            max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
            fetch_snapshot=fetch,
        )

        self.assertIsNone(resolution.snapshot)
        self.assertEqual({"source": "offline"}, resolution.freshness)

    def test_offline_and_explicit_snapshot_conflict(self) -> None:
        with self.assertRaisesRegex(FreshnessError, "cannot be used together"):
            resolve_snapshot(
                manifest(item("T-1")),
                snapshot_path="somewhere.json",
                offline=True,
                max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
                fetch_snapshot=lambda: _snapshot(),
            )

    def test_cache_hit_never_calls_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "observed-snapshot.json"
            data = manifest(item("T-1"))
            snapshot = _snapshot(_issue("T-1", 1))
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            write_cache(
                cache_path, data, snapshot, observed_at=utc_now_iso(now=now - timedelta(seconds=5))
            )

            def fetch():
                raise AssertionError("must not fetch on a cache hit")

            resolution = resolve_snapshot(
                data,
                snapshot_path=None,
                offline=False,
                max_age_seconds=300,
                fetch_snapshot=fetch,
                cache_path=cache_path,
                now=now,
            )

            self.assertEqual(snapshot, resolution.snapshot)
            self.assertEqual("cache", resolution.freshness["source"])
            self.assertEqual(5, resolution.freshness["age_seconds"])

    def test_cache_expired_fetches_and_refreshes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "observed-snapshot.json"
            data = manifest(item("T-1"))
            stale_snapshot = _snapshot(_issue("T-1", 1))
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            write_cache(
                cache_path,
                data,
                stale_snapshot,
                observed_at=utc_now_iso(now=now - timedelta(seconds=301)),
            )
            fresh_snapshot = _snapshot(_issue("T-1", 1, title="fresh"))

            resolution = resolve_snapshot(
                data,
                snapshot_path=None,
                offline=False,
                max_age_seconds=300,
                fetch_snapshot=lambda: fresh_snapshot,
                cache_path=cache_path,
                now=now,
            )

            self.assertEqual(fresh_snapshot, resolution.snapshot)
            self.assertEqual("fetched", resolution.freshness["source"])
            reloaded = read_cache(cache_path)
            self.assertEqual(fresh_snapshot, reloaded["snapshot"])

    def test_target_mismatch_fetches_even_though_cache_is_young(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "observed-snapshot.json"
            other = manifest(item("T-1"))
            other["github"]["project_number"] = 99
            now = datetime(2026, 1, 1, tzinfo=timezone.utc)
            write_cache(cache_path, other, _snapshot(), observed_at=utc_now_iso(now=now))

            data = manifest(item("T-1"))
            fresh_snapshot = _snapshot(_issue("T-1", 1))
            resolution = resolve_snapshot(
                data,
                snapshot_path=None,
                offline=False,
                max_age_seconds=300,
                fetch_snapshot=lambda: fresh_snapshot,
                cache_path=cache_path,
                now=now,
            )

            self.assertEqual(fresh_snapshot, resolution.snapshot)
            self.assertEqual("fetched", resolution.freshness["source"])

    def test_fetch_failure_raises_freshness_error_with_offline_hint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "observed-snapshot.json"

            def fetch():
                raise RuntimeError("GH_TOKEN is not set")

            with self.assertRaisesRegex(FreshnessError, "--offline"):
                resolve_snapshot(
                    manifest(item("T-1")),
                    snapshot_path=None,
                    offline=False,
                    max_age_seconds=300,
                    fetch_snapshot=fetch,
                    cache_path=cache_path,
                )
            # A failed fetch must not leave a cache behind to be read as fresh.
            self.assertIsNone(read_cache(cache_path))

    def test_no_cache_and_no_offline_fetches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "observed-snapshot.json"
            fresh_snapshot = _snapshot(_issue("T-1", 1))

            resolution = resolve_snapshot(
                manifest(item("T-1")),
                snapshot_path=None,
                offline=False,
                max_age_seconds=300,
                fetch_snapshot=lambda: fresh_snapshot,
                cache_path=cache_path,
            )

            self.assertEqual(fresh_snapshot, resolution.snapshot)
            self.assertEqual("fetched", resolution.freshness["source"])


class ManifestBehindTests(unittest.TestCase):
    def test_no_unknown_issues_returns_none(self) -> None:
        data = manifest(item("T-1"))
        snapshot = _snapshot(_issue("T-1", 1))
        self.assertIsNone(manifest_behind(data, snapshot))

    def test_reports_an_unknown_managed_issue(self) -> None:
        data = manifest(item("T-1"))
        snapshot = _snapshot(_issue("T-1", 1), _issue("T-2", 2))

        behind = manifest_behind(data, snapshot)

        self.assertIsNotNone(behind)
        self.assertEqual(
            [{"item_id": "T-2", "number": 2}], behind["unknown_managed_issues"]
        )
        self.assertIn("hint", behind)

    def test_issues_without_a_marker_are_ignored(self) -> None:
        data = manifest(item("T-1"))
        snapshot = _snapshot(_issue("T-1", 1), {"abk_id": None, "number": 5})
        self.assertIsNone(manifest_behind(data, snapshot))

    def test_multiple_unknown_issues_are_sorted(self) -> None:
        data = manifest(item("T-1"))
        snapshot = _snapshot(_issue("T-1", 1), _issue("T-9", 9), _issue("T-2", 2))

        behind = manifest_behind(data, snapshot)

        self.assertEqual(
            ["T-2", "T-9"],
            [entry["item_id"] for entry in behind["unknown_managed_issues"]],
        )


if __name__ == "__main__":
    unittest.main()
