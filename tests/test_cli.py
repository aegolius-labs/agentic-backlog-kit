from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from agentic_backlog_kit.bootstrap import build_bootstrap_plan
from agentic_backlog_kit.cli import main
from agentic_backlog_kit.iterations import build_iteration_plan
from agentic_backlog_kit.scaffold import build_scaffold_plan
from agentic_backlog_kit.sync import build_sync_plan

from tests.helpers import item, manifest


class CliTests(unittest.TestCase):
    def test_init_plan_bounds_discovery_for_gh_and_api_backends(self) -> None:
        discovery = {
            "organization": {"login": "aegolius-labs", "id": "ORG_1"},
            "repository": {"name": "example", "id": "REPO_1"},
            "projects": [
                {
                    "id": "PROJECT_7",
                    "number": 7,
                    "title": "example",
                    "url": "url-7",
                    "closed": False,
                    "linked": True,
                    "fields": [],
                    "views": [],
                }
            ],
            "labels": [],
        }
        for backend in ("gh", "api"):
            with self.subTest(backend=backend):
                transport = object()
                transport_factory = Mock(return_value=transport)
                reader = Mock()
                reader.return_value.read.return_value = discovery
                with (
                    patch("agentic_backlog_kit.cli._transport", transport_factory),
                    patch(
                        "agentic_backlog_kit.cli.GitHubProjectDiscoveryReader",
                        reader,
                    ),
                    redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(
                        0,
                        main(
                            [
                                "init-plan",
                                "--owner",
                                "aegolius-labs",
                                "--repository",
                                "example",
                                "--project-number",
                                "7",
                                "--backend",
                                backend,
                            ]
                        ),
                    )

                transport_factory.assert_called_once_with(backend)
                reader.assert_called_once_with(
                    transport,
                    owner="aegolius-labs",
                    repository="example",
                    project_title=None,
                    project_number=7,
                )

    def test_iteration_apply_refreshes_then_verifies_identity_convergence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            plan_path = root / "iteration-plan.json"
            receipt_path = root / "iteration-receipt.json"
            data = manifest()
            data["workflow"]["iteration"] = {
                "field": "Sprint",
                "start_date": "2026-08-03",
                "duration_days": 14,
            }
            old = {
                "id": "ITER_10",
                "title": "Sprint 10",
                "start_date": "2026-08-17",
                "duration_days": 14,
                "completed": False,
            }
            field = {
                "id": "FIELD_SPRINT",
                "name": "Sprint",
                "data_type": "ITERATION",
                "iteration_configuration": {
                    "start_date": "2026-08-03",
                    "duration_days": 14,
                    "iterations": [old],
                    "completed_iterations": [],
                },
            }
            before = {"fields": [field], "views": [], "labels": []}
            after = {
                "fields": [
                    {
                        **field,
                        "iteration_configuration": {
                            **field["iteration_configuration"],
                            "iterations": [
                                old,
                                {
                                    "id": "ITER_11",
                                    "title": "Sprint 11",
                                    "start_date": "2026-08-31",
                                    "duration_days": 14,
                                    "completed": False,
                                },
                            ],
                        },
                    }
                ],
                "views": [],
                "labels": [],
            }
            plan = build_iteration_plan(
                data, before, target="@next", as_of="2026-08-27"
            )
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            plan_path.write_text(json.dumps(plan.as_dict()), encoding="utf-8")
            reader = Mock()
            reader.return_value.read.side_effect = [before, after]

            with (
                patch("agentic_backlog_kit.cli._transport", return_value=object()),
                patch("agentic_backlog_kit.cli.GitHubScaffoldSnapshotReader", reader),
                patch("agentic_backlog_kit.cli.GitHubService"),
                patch(
                    "agentic_backlog_kit.cli.GitHubScaffoldExecutor",
                    return_value=lambda action: None,
                ),
                redirect_stdout(io.StringIO()) as output,
            ):
                result = main(
                    [
                        "iteration-apply",
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
            self.assertEqual(2, reader.return_value.read.call_count)
            self.assertTrue(json.loads(output.getvalue())["verified"])
            self.assertEqual("completed", json.loads(receipt_path.read_text())["status"])

    def test_init_apply_captures_created_number_and_emits_fresh_scaffold_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path = root / "bootstrap-plan.json"
            manifest_path = root / "manifest.json"
            scaffold_path = root / "scaffold-plan.json"
            receipt_path = root / "init-receipt.json"
            plan = build_bootstrap_plan(
                "aegolius-labs",
                "example",
                {
                    "organization": {"login": "aegolius-labs", "id": "ORG_1"},
                    "repository": {"name": "example", "id": "REPO_1"},
                    "projects": [],
                    "labels": [],
                },
            )
            plan_path.write_text(json.dumps(plan.as_dict()), encoding="utf-8")
            transport = InitApplyTransport()

            with patch("agentic_backlog_kit.cli._transport", return_value=transport):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        0,
                        main(
                            [
                                "init-apply",
                                "--manifest",
                                str(manifest_path),
                                "--plan",
                                str(plan_path),
                                "--confirm",
                                plan.digest,
                                "--scaffold-plan",
                                str(scaffold_path),
                                "--receipt",
                                str(receipt_path),
                            ]
                        ),
                    )

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            scaffold = json.loads(scaffold_path.read_text(encoding="utf-8"))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(11, manifest["github"]["project_number"])
            self.assertGreater(scaffold["action_count"], 0)
            self.assertEqual("completed", receipt["status"])

    def test_init_plan_can_start_with_owner_and_repository_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot_path = Path(directory) / "discovery.json"
            plan_path = Path(directory) / "bootstrap-plan.json"
            snapshot_path.write_text(
                json.dumps(
                    {
                        "organization": {"login": "aegolius-labs", "id": "ORG_1"},
                        "repository": {"name": "example", "id": "REPO_1"},
                        "projects": [],
                        "labels": [],
                    }
                ),
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    0,
                    main(
                        [
                            "init-plan",
                            "--owner",
                            "aegolius-labs",
                            "--repository",
                            "example",
                            "--snapshot",
                            str(snapshot_path),
                            "--output",
                            str(plan_path),
                        ]
                    ),
                )

            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual("project.create", plan["actions"][0]["kind"])
            self.assertEqual("example", plan["actions"][0]["payload"]["title"])

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


class InitApplyTransport:
    def __init__(self) -> None:
        self.graphql_count = 0

    def graphql(self, query: str, variables: dict):
        self.graphql_count += 1
        if "DiscoverProjects" in query:
            return {
                "organization": {
                    "id": "ORG_1",
                    "projectsV2": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
                "repository": {
                    "id": "REPO_1",
                    "name": "example",
                    "projectsV2": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            }
        if "CreateProject" in query:
            return {
                "createProjectV2": {
                    "projectV2": {
                        "id": "PROJECT_11",
                        "number": 11,
                        "title": "example",
                        "url": "project-url",
                    }
                }
            }
        return {
            "organization": {
                "projectV2": {
                    "fields": {"nodes": []},
                    "views": {"nodes": []},
                }
            }
        }

    def rest(self, method: str, path: str, payload=None):
        return []


if __name__ == "__main__":
    unittest.main()
