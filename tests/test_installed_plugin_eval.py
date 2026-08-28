from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "evals" / "installed_plugin"


class InstalledPluginEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import sys

        sys.path.insert(0, str(ROOT))
        from evals.installed_plugin import harness

        cls.harness = harness

    def test_corpus_covers_required_prompt_classes_and_skills(self) -> None:
        corpus = self.harness.load_corpus()
        self.assertEqual(
            {
                "direct",
                "indirect",
                "follow_up",
                "negative",
                "boundary",
                "write_confirmation",
            },
            {case["category"] for case in corpus["cases"]},
        )
        self.assertEqual(
            {
                "backlog-init",
                "backlog-ingest",
                "backlog-prioritize",
                "backlog-sprint-plan",
                "backlog-sync-github",
            },
            {
                expectation["skill"]
                for case in corpus["cases"]
                for expectation in case["expected_turns"]
                if expectation.get("skill")
            },
        )
        self.assertEqual(
            len(corpus["cases"]), len({case["id"] for case in corpus["cases"]})
        )
        self.assertTrue(all(case["fresh_task"] for case in corpus["cases"]))

    def test_prepare_suite_is_deterministic_and_materializes_workspace_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.harness.prepare_suite(root / "one", run_id="r06-proof")
            second = self.harness.prepare_suite(root / "two", run_id="r06-proof")

            self.assertEqual(first, second)
            marketplace = root / "one" / first["artifacts"]["marketplace"]
            self.assertTrue(marketplace.is_file())
            data = json.loads(marketplace.read_text(encoding="utf-8"))
            self.assertEqual("r06-local", data["name"])
            self.assertEqual(1, len(data["plugins"]))
            entry = data["plugins"][0]
            self.assertEqual("agentic-backlog-kit", entry["name"])
            self.assertEqual("local", entry["source"]["source"])
            self.assertEqual("./plugins/agentic-backlog-kit", entry["source"]["path"])
            self.assertEqual("AVAILABLE", entry["policy"]["installation"])
            self.assertEqual("ON_INSTALL", entry["policy"]["authentication"])
            staged = marketplace.parent.parent.parent / "plugins" / "agentic-backlog-kit"
            self.assertEqual(
                "agentic-backlog-kit",
                json.loads(
                    (staged / ".codex-plugin" / "plugin.json").read_text(
                        encoding="utf-8"
                    )
                )["name"],
            )

    def test_static_pickup_check_resolves_skills_and_bundled_references(self) -> None:
        result = self.harness.inspect_installation(ROOT)
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(5, result["skill_count"])
        self.assertEqual([], result["missing_references"])
        self.assertTrue(result["manifest"]["skills_path_valid"])

    def test_static_pickup_rejects_reference_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / "plugin"
            (plugin / ".codex-plugin").mkdir(parents=True)
            (plugin / "skills" / "sample" / "agents").mkdir(parents=True)
            (plugin / "outside.md").write_text("outside\n", encoding="utf-8")
            (plugin / ".codex-plugin" / "plugin.json").write_text(
                json.dumps(
                    {
                        "name": "sample-plugin",
                        "version": "0.1.0",
                        "description": "fixture",
                        "author": {"name": "fixture"},
                        "skills": "./skills/",
                        "interface": {},
                    }
                ),
                encoding="utf-8",
            )
            (plugin / "skills" / "sample" / "SKILL.md").write_text(
                "---\nname: sample\ndescription: sample\n---\n\n[escape](../../outside.md)\n",
                encoding="utf-8",
            )
            (plugin / "skills" / "sample" / "agents" / "openai.yaml").write_text(
                "interface:\n  display_name: Sample\n", encoding="utf-8"
            )

            result = self.harness.inspect_installation(plugin)

        self.assertFalse(result["passed"])
        self.assertTrue(any("escapes" in value for value in result["failures"]))

    def test_cli_probe_is_read_only_and_redacts_process_output(self) -> None:
        calls: list[dict] = []

        def runner(command, **kwargs):
            calls.append({"command": list(command), **kwargs})
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="codex 26.818\n",
                stderr="Authorization: should never be retained\n",
            )

        result = self.harness.probe_codex_cli(
            executable="codex.exe", runner=runner, cwd=ROOT
        )

        self.assertEqual("passed", result["status"])
        self.assertEqual(["--help", "--version"], [call["command"][-1] for call in calls])
        self.assertNotIn("Authorization", json.dumps(result))
        self.assertTrue(all(call["capture_output"] for call in calls))
        self.assertTrue(all(call["timeout"] <= 15 for call in calls))

    def test_cli_probe_records_access_denied_without_raising(self) -> None:
        def runner(command, **kwargs):
            raise PermissionError("Access is denied")

        result = self.harness.probe_codex_cli(
            executable="codex.exe", runner=runner, cwd=ROOT
        )

        self.assertEqual("blocked", result["status"])
        self.assertIn("denied", result["reason"].lower())

    def test_diagnostics_keeps_static_pass_separate_from_blocked_cli_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            suite = self.harness.prepare_suite(Path(temporary), run_id="diagnostic-proof")

            def runner(command, **kwargs):
                raise PermissionError("Access is denied")

            with patch.object(self.harness, "subprocess") as process:
                process.run.side_effect = runner
                diagnostics = self.harness.run_diagnostics(
                    suite,
                    suite_root=Path(temporary),
                    run_cli=True,
                    executable="codex.exe",
                )

        self.assertTrue(diagnostics["static_pickup"]["passed"])
        self.assertTrue(diagnostics["marketplace"]["passed"])
        self.assertEqual("blocked", diagnostics["codex_cli"]["status"])
        self.assertFalse(diagnostics["passed"])

    def test_synthetic_results_verify_every_case_and_are_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            suite = self.harness.prepare_suite(Path(temporary), run_id="result-proof")
            results = self.harness.synthetic_results(suite)
            report = self.harness.verify_results(suite, results)
            repeated = self.harness.verify_results(suite, copy.deepcopy(results))

        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report, repeated)
        self.assertEqual(len(suite["cases"]), report["case_count"])
        self.assertTrue(all(value["passed"] for value in report["cases"]))
        self.assertEqual(
            {"mcp_available", "mcp_unavailable"},
            {
                run["mode"]
                for result in results
                for run in result["executor_runs"]
            },
        )

    def test_verifier_rejects_unsupported_activation_and_unauthorized_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            suite = self.harness.prepare_suite(Path(temporary), run_id="negative-proof")
            results = self.harness.synthetic_results(suite)
            negative = next(
                value
                for value in results
                if value["case_id"] == "negative-weather"
            )
            negative["executor_runs"][0]["turns"][0]["activated"] = True
            negative["executor_runs"][0]["turns"][0]["skill"] = "backlog-ingest"
            write_case = next(
                value
                for value in results
                if value["case_id"] == "write-without-confirmation"
            )
            write_case["executor_runs"][0]["turns"][0]["authorization"]["mutated"] = True
            report = self.harness.verify_results(suite, results)

        self.assertFalse(report["passed"])
        self.assertTrue(any("negative-weather" in value for value in report["failures"]))
        self.assertTrue(
            any("write-without-confirmation" in value for value in report["failures"])
        )

    def test_verifier_rejects_missing_duplicate_and_nonfresh_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            suite = self.harness.prepare_suite(Path(temporary), run_id="shape-proof")
            results = self.harness.synthetic_results(suite)
            results.pop()
            results.append(copy.deepcopy(results[0]))
            results[0]["fresh_task"] = False
            report = self.harness.verify_results(suite, results)

        self.assertFalse(report["passed"])
        self.assertTrue(any("duplicate" in value for value in report["failures"]))
        self.assertTrue(any("missing" in value for value in report["failures"]))
        self.assertTrue(any("fresh task" in value for value in report["failures"]))

    def test_write_confirmation_requires_exact_digest_when_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            suite = self.harness.prepare_suite(Path(temporary), run_id="confirm-proof")
            results = self.harness.synthetic_results(suite)
            confirmed = next(
                value
                for value in results
                if value["case_id"] == "write-with-confirmation"
            )
            confirmed["executor_runs"][0]["turns"][1]["confirmation"][
                "confirmed_digest"
            ] = "f" * 64
            report = self.harness.verify_results(suite, results)

        self.assertFalse(report["passed"])
        self.assertTrue(any("digest" in value for value in report["failures"]))

    def test_cli_prepare_show_and_verify_are_local_only(self) -> None:
        from scripts import installed_plugin_eval

        personal_marketplace = Path.home() / ".agents" / "plugins" / "marketplace.json"
        personal_before = (
            personal_marketplace.read_bytes() if personal_marketplace.exists() else None
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "suite"
            self.assertEqual(0, installed_plugin_eval.main(["prepare", "--output", str(output)]))
            self.assertEqual(
                0,
                installed_plugin_eval.main(
                    ["show", "--suite", str(output / "suite.json")]
                ),
            )
            self.assertNotEqual(
                0,
                installed_plugin_eval.main(
                    ["verify", "--suite", str(output / "suite.json")]
                ),
            )
        personal_after = (
            personal_marketplace.read_bytes() if personal_marketplace.exists() else None
        )
        self.assertEqual(personal_before, personal_after)


if __name__ == "__main__":
    unittest.main()
