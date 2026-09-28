"""S-R35-3: `abk observe` CLI wiring.

Exercises `observe`'s freshness resolution (same seam as planning commands:
`--offline-snapshot`, the auto-refreshed cache) and its route labeling,
without touching the network - the same `_read_snapshot` patch seam
`tests/test_freshness_cli.py` uses for planning commands.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from agentic_backlog_kit.cli import main
from agentic_backlog_kit.freshness import DEFAULT_CACHE_PATH

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


class ObserveCliTests(unittest.TestCase):
    def test_auto_fetch_labels_the_route_with_the_resolved_backend(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            data = manifest(item("T-1"))
            _write_manifest(manifest_path, data)
            snapshot = {
                "issues": [
                    {
                        "abk_id": "T-1",
                        "number": 1,
                        "state": "open",
                        "in_project": False,
                    }
                ],
                "unmanaged_issue_count": 0,
            }

            with (
                _chdir(root),
                patch(
                    "agentic_backlog_kit.cli._read_snapshot", return_value=snapshot
                ),
                redirect_stdout(io.StringIO()) as output,
            ):
                result = main(
                    ["observe", "--manifest", str(manifest_path), "--backend", "gh"]
                )
                document = json.loads(output.getvalue())

            self.assertEqual(0, result)
            self.assertEqual("abk-observed-state", document["contract"])
            self.assertEqual("gh", document["source"]["route"])
            self.assertEqual("T-1", document["items"][0]["item_id"])
            self.assertTrue((root / DEFAULT_CACHE_PATH).exists())

    def test_cache_hit_labels_the_route_as_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            _write_manifest(manifest_path, manifest(item("T-1")))
            snapshot = {"issues": [], "unmanaged_issue_count": 0}

            with (
                _chdir(root),
                patch(
                    "agentic_backlog_kit.cli._read_snapshot", return_value=snapshot
                ) as reader,
            ):
                with redirect_stdout(io.StringIO()):
                    main(["observe", "--manifest", str(manifest_path)])
                with redirect_stdout(io.StringIO()) as second_output:
                    main(["observe", "--manifest", str(manifest_path)])
                    document = json.loads(second_output.getvalue())

            reader.assert_called_once()
            self.assertEqual("cache", document["source"]["route"])

    def test_offline_snapshot_labels_the_route_and_never_fetches(self) -> None:
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
                                "state": "open",
                                "in_project": False,
                            }
                        ],
                        "unmanaged_issue_count": 0,
                    }
                ),
                encoding="utf-8",
            )

            def fail(*args, **kwargs):
                raise AssertionError("must not fetch with --offline-snapshot")

            with (
                _chdir(root),
                patch("agentic_backlog_kit.cli._read_snapshot", side_effect=fail),
                redirect_stdout(io.StringIO()) as output,
            ):
                result = main(
                    [
                        "observe",
                        "--manifest",
                        str(manifest_path),
                        "--offline-snapshot",
                        str(snapshot_path),
                    ]
                )
                document = json.loads(output.getvalue())

            self.assertEqual(0, result)
            self.assertEqual("offline-snapshot", document["source"]["route"])
            self.assertIn("observed_at", document)
            self.assertFalse((root / DEFAULT_CACHE_PATH).exists())

    def test_output_path_writes_the_document_and_prints_a_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            output_path = root / "observed-state.json"
            _write_manifest(manifest_path, manifest(item("T-1")))
            snapshot = {
                "issues": [
                    {
                        "abk_id": "T-1",
                        "number": 1,
                        "state": "open",
                        "in_project": False,
                    }
                ],
                "unmanaged_issue_count": 0,
            }

            with (
                _chdir(root),
                patch(
                    "agentic_backlog_kit.cli._read_snapshot", return_value=snapshot
                ),
                redirect_stdout(io.StringIO()) as output,
            ):
                result = main(
                    [
                        "observe",
                        "--manifest",
                        str(manifest_path),
                        "--output",
                        str(output_path),
                    ]
                )
                summary = json.loads(output.getvalue())

            self.assertEqual(0, result)
            self.assertTrue(output_path.exists())
            written = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual("abk-observed-state", written["contract"])
            self.assertEqual(written["digest"], summary["digest"])
            self.assertEqual(1, summary["items"])


if __name__ == "__main__":
    unittest.main()
