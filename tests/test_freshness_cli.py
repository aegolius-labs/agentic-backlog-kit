"""S-R35-1: CLI wiring for fresh-by-default planning (owner decision D1).

These tests exercise `agentic_backlog_kit.cli` end to end for the new
resolution order - explicit snapshot, `--offline`, and the auto-refreshed
cache - using the same `_read_snapshot`/`_transport` patch seams the rest of
`tests/test_cli.py` already uses. Pure `freshness` module behavior is covered
by `tests/test_freshness.py`; this file covers wiring: argument parsing,
JSON output shape, and cache side effects on disk.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from agentic_backlog_kit.cli import main
from agentic_backlog_kit.freshness import DEFAULT_CACHE_PATH, read_cache
from agentic_backlog_kit.sync import build_sync_plan

from tests.helpers import item, manifest


@contextlib.contextmanager
def _chdir(path: Path):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _write_manifest(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


class PrioritizeFreshnessCliTests(unittest.TestCase):
    def test_auto_mode_fetches_and_writes_the_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            data = manifest(item("T-1"))
            _write_manifest(manifest_path, data)
            snapshot = {"issues": []}

            with (
                _chdir(root),
                patch(
                    "agentic_backlog_kit.cli._read_snapshot", return_value=snapshot
                ) as reader,
                redirect_stdout(io.StringIO()) as output,
            ):
                result = main(
                    ["prioritize", "--manifest", str(manifest_path), "--limit", "5"]
                )
                payload = json.loads(output.getvalue())

            self.assertEqual(0, result)
            reader.assert_called_once()
            call_args = reader.call_args.args
            self.assertIsNone(call_args[0])
            self.assertEqual("auto", call_args[2])
            self.assertEqual("github", payload["operational_state"])
            self.assertEqual("fetched", payload["freshness"]["source"])
            self.assertIn("observed_at", payload["freshness"])
            self.assertIn("age_seconds", payload["freshness"])
            cache = read_cache(root / DEFAULT_CACHE_PATH)
            self.assertIsNotNone(cache)
            self.assertEqual(snapshot, cache["snapshot"])

    def test_a_second_call_within_max_age_reads_the_cache_and_never_refetches(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            data = manifest(item("T-1"))
            _write_manifest(manifest_path, data)
            snapshot = {"issues": []}

            with (
                _chdir(root),
                patch(
                    "agentic_backlog_kit.cli._read_snapshot", return_value=snapshot
                ) as reader,
                redirect_stdout(io.StringIO()),
            ):
                main(["prioritize", "--manifest", str(manifest_path)])
                with redirect_stdout(io.StringIO()) as second_output:
                    main(["prioritize", "--manifest", str(manifest_path)])
                    second_payload = json.loads(second_output.getvalue())

            reader.assert_called_once()
            self.assertEqual("cache", second_payload["freshness"]["source"])

    def test_target_mismatch_refetches_even_though_the_cache_is_young(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            data = manifest(item("T-1"))
            _write_manifest(manifest_path, data)

            with (
                _chdir(root),
                patch(
                    "agentic_backlog_kit.cli._read_snapshot",
                    return_value={"issues": []},
                ),
                redirect_stdout(io.StringIO()),
            ):
                main(["prioritize", "--manifest", str(manifest_path)])

            other = manifest(item("T-1"))
            other["github"]["repository"] = "elsewhere"
            other_manifest_path = root / "other-manifest.json"
            _write_manifest(other_manifest_path, other)

            with (
                _chdir(root),
                patch(
                    "agentic_backlog_kit.cli._read_snapshot",
                    return_value={"issues": []},
                ) as reader,
                redirect_stdout(io.StringIO()) as output,
            ):
                main(["prioritize", "--manifest", str(other_manifest_path)])
                payload = json.loads(output.getvalue())

            reader.assert_called_once()
            self.assertEqual("fetched", payload["freshness"]["source"])

    def test_offline_never_reads_or_writes_the_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            _write_manifest(manifest_path, manifest(item("T-1")))

            def fail(*args, **kwargs):
                raise AssertionError("must not fetch when --offline is given")

            with (
                _chdir(root),
                patch("agentic_backlog_kit.cli._read_snapshot", side_effect=fail),
                redirect_stdout(io.StringIO()) as output,
            ):
                result = main(
                    ["prioritize", "--manifest", str(manifest_path), "--offline"]
                )
                payload = json.loads(output.getvalue())

            self.assertEqual(0, result)
            self.assertEqual("local-intent", payload["operational_state"])
            self.assertEqual({"source": "offline"}, payload["freshness"])
            self.assertIsNone(read_cache(root / DEFAULT_CACHE_PATH))

    def test_offline_and_explicit_snapshot_are_rejected_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            snapshot_path = root / "snapshot.json"
            _write_manifest(manifest_path, manifest(item("T-1")))
            snapshot_path.write_text(json.dumps({"issues": []}), encoding="utf-8")

            with (
                _chdir(root),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()) as err,
            ):
                result = main(
                    [
                        "prioritize",
                        "--manifest",
                        str(manifest_path),
                        "--offline",
                        "--operational-snapshot",
                        str(snapshot_path),
                    ]
                )

            self.assertEqual(1, result)
            failure = json.loads(err.getvalue())
            self.assertEqual("FreshnessError", failure["error"])
            self.assertIn("cannot be used together", failure["message"])

    def test_a_failed_auto_fetch_fails_closed_with_an_offline_hint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            _write_manifest(manifest_path, manifest(item("T-1")))

            def fail(*args, **kwargs):
                raise RuntimeError("GH_TOKEN is not set")

            with (
                _chdir(root),
                patch("agentic_backlog_kit.cli._read_snapshot", side_effect=fail),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()) as err,
            ):
                result = main(["prioritize", "--manifest", str(manifest_path)])

            self.assertEqual(1, result)
            failure = json.loads(err.getvalue())
            self.assertEqual("FreshnessError", failure["error"])
            self.assertIn("--offline", failure["message"])
            self.assertIsNone(read_cache(root / DEFAULT_CACHE_PATH))

    def test_explicit_snapshot_reports_manifest_behind_for_an_unknown_managed_issue(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            snapshot_path = root / "snapshot.json"
            _write_manifest(manifest_path, manifest(item("T-1")))
            snapshot_path.write_text(
                json.dumps(
                    {
                        "issues": [
                            {
                                "abk_id": "T-1",
                                "number": 1,
                                "in_project": False,
                                "project_fields": {},
                            },
                            {
                                "abk_id": "T-9",
                                "number": 9,
                                "in_project": False,
                                "project_fields": {},
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with (
                _chdir(root),
                redirect_stdout(io.StringIO()) as output,
            ):
                result = main(
                    [
                        "prioritize",
                        "--manifest",
                        str(manifest_path),
                        "--operational-snapshot",
                        str(snapshot_path),
                    ]
                )
                payload = json.loads(output.getvalue())

            self.assertEqual(0, result)
            self.assertIn("manifest_behind", payload)
            self.assertEqual(
                [{"item_id": "T-9", "number": 9}],
                payload["manifest_behind"]["unknown_managed_issues"],
            )

    def test_next_and_gantt_and_sprint_plan_also_carry_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            _write_manifest(manifest_path, manifest(item("T-1")))

            with (
                _chdir(root),
                patch(
                    "agentic_backlog_kit.cli._read_snapshot",
                    return_value={"issues": []},
                ),
            ):
                with redirect_stdout(io.StringIO()) as next_output:
                    self.assertEqual(
                        0,
                        main(
                            ["next", "--manifest", str(manifest_path), "--offline"]
                        ),
                    )
                next_payload = json.loads(next_output.getvalue())

                with redirect_stdout(io.StringIO()) as gantt_output:
                    self.assertEqual(
                        0,
                        main(
                            [
                                "gantt",
                                "--manifest",
                                str(manifest_path),
                                "--format",
                                "json",
                                "--start",
                                "2026-01-01",
                                "--offline",
                            ]
                        ),
                    )
                gantt_payload = json.loads(gantt_output.getvalue())

                with redirect_stdout(io.StringIO()) as sprint_output:
                    self.assertEqual(
                        0,
                        main(
                            [
                                "sprint-plan",
                                "--manifest",
                                str(manifest_path),
                                "--offline",
                            ]
                        ),
                    )
                sprint_payload = json.loads(sprint_output.getvalue())

            for payload in (next_payload, gantt_payload, sprint_payload):
                self.assertEqual({"source": "offline"}, payload["freshness"])
                self.assertEqual("local-intent", payload["operational_state"])


class ApplyInvalidatesCacheTests(unittest.TestCase):
    def test_sync_apply_deletes_the_cache_after_a_successful_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            plan_path = root / "plan.json"
            receipt_path = root / "receipt.json"
            data = manifest(item("T-1"))
            snapshot = {"issues": []}
            _write_manifest(manifest_path, data)
            plan = build_sync_plan(data, snapshot)
            plan_path.write_text(json.dumps(plan.as_dict()), encoding="utf-8")

            reader = Mock()
            reader.return_value.read.return_value = snapshot

            with _chdir(root):
                cache_path = root / DEFAULT_CACHE_PATH
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(
                    json.dumps(
                        {
                            "cache_version": 1,
                            "observed_at": "2026-01-01T00:00:00Z",
                            "target": {
                                "owner": "aegolius-labs",
                                "repository": "example",
                                "project_number": 1,
                            },
                            "snapshot": snapshot,
                        }
                    ),
                    encoding="utf-8",
                )
                self.assertTrue(cache_path.exists())

                with (
                    patch(
                        "agentic_backlog_kit.cli._transport", return_value=object()
                    ),
                    patch("agentic_backlog_kit.cli.GitHubSnapshotReader", reader),
                    patch("agentic_backlog_kit.cli.GitHubService"),
                    patch(
                        "agentic_backlog_kit.cli.GitHubPlanExecutor",
                        return_value=lambda action: None,
                    ),
                    redirect_stdout(io.StringIO()),
                ):
                    result = main(
                        [
                            "sync-apply",
                            "--manifest",
                            str(manifest_path),
                            "--plan",
                            str(plan_path),
                            "--confirm",
                            plan.digest,
                            "--receipt",
                            str(receipt_path),
                        ]
                    )

                self.assertEqual(0, result)
                self.assertFalse(cache_path.exists())


if __name__ == "__main__":
    unittest.main()
