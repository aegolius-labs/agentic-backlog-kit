from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agentic_backlog_kit.manifest import validate_manifest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = REPOSITORY_ROOT / "evals" / "live_github"


class LiveGitHubEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import sys

        sys.path.insert(0, str(REPOSITORY_ROOT))
        from evals.live_github import harness

        cls.harness = harness

    def _write_complete_evidence(self, root: Path, suite: dict, variant: dict) -> None:
        evidence = root / variant["name"] / "evidence"
        template = json.loads(
            (EVAL_ROOT / "fixtures" / "manifest.template.json").read_text(
                encoding="utf-8"
            )
        )
        manifest = self.harness.materialize_manifest(
            template,
            owner=suite["owner"],
            repository=variant["repository"],
            project_number=17 if variant["name"] == "native" else 18,
            issue_type_mode=variant["name"],
            iteration_start=suite["iteration_start"],
        )
        expected = json.loads(
            (EVAL_ROOT / "expected-state.json").read_text(encoding="utf-8")
        )

        def write(relative: str, value: dict) -> None:
            path = evidence / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

        write("manifest.json", manifest)
        write(
            "preflight.json",
            {"passed": True, "backend": "gh", "redactions_confirmed": True},
        )
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "commands.ndjson").write_text(
            '{"step":"preflight","exit_code":0,"redacted":true}\n',
            encoding="utf-8",
        )
        for stage in ("bootstrap", "scaffold", "sync"):
            digest = "a" * 64
            write(f"{stage}/plan.json", {"digest": digest, "actions": [{}]})
            write(
                f"{stage}/receipt.json",
                {
                    "plan_digest": digest,
                    "status": "completed",
                    "total_actions": 1,
                    "applied_actions": 1,
                    "completed_actions": [{}],
                },
            )
        fields = [dict(value) for value in expected["fields"]]
        sprint = next(value for value in fields if value["name"] == "Sprint")
        sprint["id"] = "PVTF_sprint"
        sprint["database_id"] = 123
        sprint["iteration_configuration"] = {
            "start_date": suite["iteration_start"],
            "duration_days": 14,
            "iterations": [
                {
                    "id": "ITER_1",
                    "title": "Sprint 1",
                    "start_date": suite["iteration_start"],
                    "duration_days": 14,
                    "completed": False,
                },
                {
                    "id": "ITER_2",
                    "title": "Sprint 2",
                    "start_date": "2026-09-21",
                    "duration_days": 14,
                    "completed": False,
                },
            ],
            "completed_iterations": [],
        }
        write(
            "scaffold/after.json",
            {
                "fields": fields,
                "views": expected["views"],
                "labels": [
                    {"name": value} for value in expected["required_type_labels"]
                ],
            },
        )
        write("scaffold/second-plan.json", {"action_count": 0, "actions": []})
        write("ingestion/result.json", {"item_ids": variant["expected_item_ids"]})
        write(
            "prioritization/result.json",
            {"items": [{"id": value} for value in variant["expected_priority_ids"]]},
        )
        write(
            "sprint/plan.json",
            {"items": [{"id": value} for value in variant["expected_sprint_ids"]]},
        )
        write(
            "iterations/assertions.json",
            {
                "current_resolved": True,
                "next_resolved": True,
                "completed_rejected": True,
                "duplicate_rejected": True,
                "overlap_rejected": True,
                "incomplete_metadata_rejected": True,
                "extension_applied": True,
                "server_identities_verified": True,
                "second_plan_zero": True,
            },
        )
        issues = []
        for item in manifest["items"]:
            issue = {
                "abk_id": item["id"],
                "type": item["type"] if variant["name"] == "native" else None,
                "labels": (
                    []
                    if variant["name"] == "native"
                    else [f"type:{item['type'].lower()}"]
                ),
                "parent_abk_id": item["parent"],
                "depends_on_abk_ids": item["depends_on"],
                "project_fields": {"Status": item["status"]},
            }
            issue["project_fields"].update(
                {
                    "Impact": item["impact"],
                    "Effort": item["effort"],
                    "Business Value": item["business_value"],
                    "Enabler Value": item["enabler_value"],
                }
            )
            if item["sprint"]:
                issue["project_fields"]["Sprint"] = item["sprint"]
            issues.append(issue)
        from agentic_backlog_kit.priority import prioritize

        priorities = {value.id: value.priority_score for value in prioritize(manifest)}
        for issue in issues:
            issue["project_fields"]["Priority"] = priorities[issue["abk_id"]]
        write("sync/after.json", {"issues": issues})
        write("sync/second-plan.json", {"action_count": 0, "actions": []})
        write("assertions.json", {"passed": True})

    def test_manifest_fixture_materializes_valid_native_and_label_variants(self) -> None:
        template = json.loads(
            (EVAL_ROOT / "fixtures" / "manifest.template.json").read_text(
                encoding="utf-8"
            )
        )

        native = self.harness.materialize_manifest(
            template,
            owner="aegolius-labs",
            repository="abk-eval-native",
            project_number=17,
            issue_type_mode="native",
            iteration_start="2026-09-07",
        )
        labels = self.harness.materialize_manifest(
            template,
            owner="aegolius-labs",
            repository="abk-eval-labels",
            project_number=18,
            issue_type_mode="labels",
            iteration_start="2026-09-07",
        )

        self.assertEqual("native", validate_manifest(native)["github"]["issue_type_mode"])
        self.assertEqual("labels", validate_manifest(labels)["github"]["issue_type_mode"])
        self.assertEqual(
            {"Initiative", "Epic", "Feature", "Story", "Bug", "Task"},
            {item["type"] for item in native["items"]},
        )
        by_id = {item["id"]: item for item in native["items"]}
        self.assertEqual("STORY-0001", by_id["TASK-0002"]["parent"])
        self.assertEqual(["TASK-0001"], by_id["TASK-0002"]["depends_on"])

    def test_resource_names_are_deterministic_bounded_and_seed_specific(self) -> None:
        first = self.harness.resource_names("release candidate 42", "native")
        again = self.harness.resource_names("release candidate 42", "native")
        other = self.harness.resource_names("release candidate 43", "native")

        self.assertEqual(first, again)
        self.assertNotEqual(first, other)
        self.assertRegex(first["repository"], r"^abk-eval-[a-z0-9-]+-native$")
        self.assertLessEqual(len(first["repository"]), 100)
        self.assertIn(first["token"], first["project_title"])

    def test_prepared_suite_covers_lifecycle_and_all_backends(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            suite = self.harness.prepare_suite(
                Path(temporary),
                owner="aegolius-labs",
                run_id="wave-c-2026-09-07-001",
                iteration_start="2026-09-07",
                backend="gh",
            )
            repeated = self.harness.prepare_suite(
                Path(temporary) / "repeat",
                owner="aegolius-labs",
                run_id="wave-c-2026-09-07-001",
                iteration_start="2026-09-07",
                backend="gh",
            )

            self.assertEqual(suite, repeated)
            self.assertFalse(suite["mutation_authorized"])
            self.assertEqual("gh", suite["selected_backend"])
            self.assertEqual(["api", "gh", "mcp"], sorted(suite["backend_matrix"]))
            capabilities = set(suite["coverage"])
            self.assertTrue(
                {
                    "bootstrap",
                    "scaffold",
                    "ingestion",
                    "prioritization",
                    "sprint_planning",
                    "sync_apply_verify",
                    "second_plan_zero",
                    "hierarchy",
                    "dependencies",
                    "fields",
                    "iterations",
                    "views",
                    "native_issue_types",
                    "label_fallback",
                }.issubset(capabilities)
            )
            mutating = [step for step in suite["steps"] if step["mutates"]]
            self.assertTrue(mutating)
            self.assertTrue(
                all(step["confirmation"] == "reviewed-plan-digest" for step in mutating)
            )
            self.assertNotEqual(
                suite["execution_confirmation"], suite["cleanup_confirmation"]
            )

    def test_default_run_never_calls_runner_and_execution_needs_exact_digest(self) -> None:
        calls: list[dict] = []

        def runner(step: dict) -> None:
            calls.append(step)

        with tempfile.TemporaryDirectory() as temporary:
            suite = self.harness.prepare_suite(
                Path(temporary),
                owner="aegolius-labs",
                run_id="dry-run-proof",
                iteration_start="2026-09-07",
                backend="gh",
            )
            result = self.harness.run_suite(suite, runner=runner)
            self.assertEqual("dry-run", result["status"])
            self.assertEqual([], calls)

            with self.assertRaisesRegex(self.harness.EvaluationSafetyError, "digest"):
                self.harness.run_suite(
                    suite, execute=True, confirmation="wrong", runner=runner
                )
            self.assertEqual([], calls)
            with self.assertRaisesRegex(
                self.harness.EvaluationSafetyError, "reviewed plan digest"
            ):
                self.harness.run_suite(
                    suite,
                    execute=True,
                    confirmation=suite["execution_confirmation"],
                    runner=runner,
                )
            self.assertEqual([], calls)

    def test_cleanup_requires_distinct_exact_confirmation(self) -> None:
        calls: list[dict] = []
        with tempfile.TemporaryDirectory() as temporary:
            suite = self.harness.prepare_suite(
                Path(temporary),
                owner="aegolius-labs",
                run_id="cleanup-proof",
                iteration_start="2026-09-07",
                backend="gh",
            )
            with self.assertRaisesRegex(self.harness.EvaluationSafetyError, "cleanup"):
                self.harness.run_cleanup(
                    suite,
                    confirmation=suite["execution_confirmation"],
                    runner=calls.append,
                )
            with self.assertRaisesRegex(
                self.harness.EvaluationSafetyError, "evidence"
            ):
                self.harness.run_cleanup(
                    suite,
                    confirmation=suite["cleanup_confirmation"],
                    runner=calls.append,
                )
        self.assertEqual([], calls)

    def test_evidence_contract_accepts_complete_synthetic_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            suite = self.harness.prepare_suite(
                root,
                owner="aegolius-labs",
                run_id="evidence-proof",
                iteration_start="2026-09-07",
                backend="gh",
            )
            for variant in suite["variants"]:
                self._write_complete_evidence(root, suite, variant)

            report = self.harness.verify_evidence(root, suite)

        self.assertTrue(report["passed"])
        self.assertEqual([], report["failures"])
        self.assertTrue(all(result["passed"] for result in report["variants"]))

    def test_evidence_contract_rejects_drift_and_nonzero_second_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            suite = self.harness.prepare_suite(
                root,
                owner="aegolius-labs",
                run_id="negative-evidence-proof",
                iteration_start="2026-09-07",
                backend="gh",
            )
            for variant in suite["variants"]:
                self._write_complete_evidence(root, suite, variant)
            native = root / "native" / "evidence"
            second_plan = native / "sync" / "second-plan.json"
            second_plan.write_text(
                json.dumps({"action_count": 1, "actions": [{"kind": "issue.update"}]})
                + "\n",
                encoding="utf-8",
            )
            after_path = native / "scaffold" / "after.json"
            after = json.loads(after_path.read_text(encoding="utf-8"))
            next(view for view in after["views"] if view["name"] == "Kanban")[
                "filter"
            ] = "is:issue"
            after_path.write_text(json.dumps(after) + "\n", encoding="utf-8")

            report = self.harness.verify_evidence(root, suite)

        self.assertFalse(report["passed"])
        self.assertTrue(
            any("Kanban configuration differs" in value for value in report["failures"])
        )
        self.assertTrue(
            any("second sync plan is not empty" in value for value in report["failures"])
        )

    def test_expected_state_requires_full_view_iteration_and_type_assertions(self) -> None:
        expected = json.loads(
            (EVAL_ROOT / "expected-state.json").read_text(encoding="utf-8")
        )
        view_names = {view["name"] for view in expected["views"]}
        field_names = {field["name"] for field in expected["fields"]}

        self.assertEqual(
            {"Backlog", "Kanban", "Current Sprint", "Roadmap"}, view_names
        )
        self.assertTrue(
            {"layout", "filter", "visible_fields", "sort_by", "group_by"}.issubset(
                expected["view_assertion_dimensions"]
            )
        )
        self.assertTrue(
            {"Status", "Sprint", "Impact", "Effort", "Business Value", "Enabler Value", "Priority"}.issubset(
                field_names
            )
        )
        self.assertEqual("@current", expected["iterations"]["required_alias"])
        self.assertEqual("native", expected["issue_type_assertions"]["native"]["mode"])
        self.assertEqual("labels", expected["issue_type_assertions"]["labels"]["mode"])


if __name__ == "__main__":
    unittest.main()
