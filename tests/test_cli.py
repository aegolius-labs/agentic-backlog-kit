from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from agentic_backlog_kit.cli import main
from agentic_backlog_kit.scaffold import build_scaffold_plan
from agentic_backlog_kit.sync import build_sync_plan

from tests.helpers import item, manifest


class CliTests(unittest.TestCase):
    def test_init_validate_and_prioritize_are_local_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "init",
                            "--manifest",
                            str(manifest_path),
                            "--owner",
                            "aegolius-labs",
                            "--repository",
                            "example",
                            "--project-number",
                            "1",
                        ]
                    ),
                )
            self.assertTrue(manifest_path.exists())

            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    0, main(["validate", "--manifest", str(manifest_path)])
                )

            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["items"] = [
                {
                    "id": "T-1",
                    "title": "First task",
                    "type": "Task",
                    "description": "Do the first useful thing",
                    "acceptance_criteria": ["A test proves it works"],
                    "parent": None,
                    "depends_on": [],
                    "impact": 3,
                    "effort": 2,
                    "business_value": 4,
                    "enabler_value": 0,
                    "status": "Ready",
                    "maturity": "ready",
                    "sprint": None,
                }
            ]
            manifest_path.write_text(json.dumps(data), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "prioritize",
                            "--manifest",
                            str(manifest_path),
                            "--limit",
                            "1",
                        ]
                    ),
                )
            result = json.loads(output.getvalue())
            self.assertEqual("T-1", result["items"][0]["id"])

    def test_init_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            manifest_path.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "already exists"):
                main(
                    [
                        "init",
                        "--manifest",
                        str(manifest_path),
                        "--owner",
                        "aegolius-labs",
                        "--repository",
                        "example",
                        "--project-number",
                        "1",
                    ]
                )
            self.assertEqual("keep", manifest_path.read_text(encoding="utf-8"))

    def test_sync_apply_refreshes_remote_state_and_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            plan_path = root / "plan.json"
            receipt_path = root / "receipt.json"
            data = manifest(item("T-1"))
            snapshot = {"issues": []}
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            plan = build_sync_plan(data, snapshot)
            plan_path.write_text(json.dumps(plan.as_dict()), encoding="utf-8")
            reader = Mock()
            reader.return_value.read.return_value = snapshot

            with (
                patch("agentic_backlog_kit.cli._transport", return_value=object()),
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
            reader.return_value.read.assert_called_once_with()
            self.assertEqual(
                "completed", json.loads(receipt_path.read_text())["status"]
            )

    def test_scaffold_apply_refreshes_remote_state_and_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            plan_path = root / "plan.json"
            receipt_path = root / "receipt.json"
            data = manifest()
            data["workflow"]["iteration"] = {
                "field": "Sprint",
                "start_date": "2026-09-07",
                "duration_days": 14,
            }
            snapshot = {"fields": [], "views": [], "labels": []}
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            plan = build_scaffold_plan(data, snapshot)
            plan_path.write_text(json.dumps(plan.as_dict()), encoding="utf-8")
            reader = Mock()
            reader.return_value.read.return_value = snapshot

            with (
                patch("agentic_backlog_kit.cli._transport", return_value=object()),
                patch("agentic_backlog_kit.cli.GitHubScaffoldSnapshotReader", reader),
                patch("agentic_backlog_kit.cli.GitHubService"),
                patch(
                    "agentic_backlog_kit.cli.GitHubScaffoldExecutor",
                    return_value=lambda action: None,
                ),
                redirect_stdout(io.StringIO()),
            ):
                result = main(
                    [
                        "scaffold-apply",
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
            reader.return_value.read.assert_called_once_with()
            self.assertEqual(
                "completed", json.loads(receipt_path.read_text())["status"]
            )


if __name__ == "__main__":
    unittest.main()
