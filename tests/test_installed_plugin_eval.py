from __future__ import annotations

import copy
import json
import subprocess
import sys
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

    def test_wave_c_r06_evidence_is_bounded_redacted_and_complete_by_category(self) -> None:
        evidence = json.loads(
            (EVAL_ROOT / "evidence.wave-c-r06.json").read_text(encoding="utf-8")
        )
        self.assertFalse(evidence["execution_scope"]["full_real_corpus_executed"])
        self.assertEqual(
            {"direct", "indirect", "follow_up", "negative", "boundary", "write_confirmation"},
            set(evidence["execution_scope"]["real_prompt_categories_observed"]),
        )
        self.assertTrue(evidence["complete_corpus_contract"]["deterministic_schema_and_verifier_tests_passed"])
        trace = evidence["durable_trace"]
        self.assertTrue(trace["passed"])
        self.assertEqual(2, trace["turn_count"])
        self.assertTrue(trace["session_identity_proven"])
        self.assertTrue(trace["continuation_reused"])
        self.assertFalse(trace["workspace_changed"])
        self.assertFalse(trace["external_contact_observed"])
        self.assertTrue(trace["session_archived"])
        self.assertTrue(trace["reused_identifiers"])
        self.assertGreater(trace["token_usage"]["input_tokens"], 0)
        self.assertFalse(evidence["credentials_recorded"])
        self.assertFalse(evidence["raw_prompts_or_session_ids_recorded"])

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

    def test_plugin_catalog_probe_rejects_valid_json_from_failed_process(self) -> None:
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(
                command,
                7,
                stdout=json.dumps({"installed": [{
                    "name": "agentic-backlog-kit", "installed": True, "enabled": True,
                    "source": {"source": "local"},
                }]}),
                stderr="catalog failed",
            )

        result = self.harness.probe_plugin_catalog(executable="codex.cmd", runner=runner)
        self.assertEqual("failed", result["status"])
        self.assertIsNone(result["plugin"])

    def test_mcp_probe_does_not_treat_unavailable_row_as_available(self) -> None:
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(
                command, 0, stdout="github MCP unavailable\n", stderr=""
            )

        result = self.harness.probe_codex_mcp(executable="codex.cmd", runner=runner)
        self.assertFalse(result["github_mcp"])

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

    def _trace_suite(self, temporary: str, run_id: str = "trace-proof") -> dict:
        return self.harness.prepare_suite(Path(temporary) / "suite", run_id=run_id)

    def _fake_trace_output(
        self,
        *,
        skill: str = "backlog-ingest",
        reference: str = "skills/backlog-ingest/references/item-contract.md",
        thread_id: str | None = "thread-trace-1",
        mutation: bool = False,
        authorization: str = "",
    ) -> str:
        events = []
        if thread_id:
            events.append({"type": "thread.started", "thread_id": thread_id})
        item = {
            "type": "file_change" if mutation else "command_execution",
            "id": "item-1",
            "command": (
                ["python", "C:/installed/agentic-backlog-kit/scripts/backlog.py", "validate", "C:/installed/agentic-backlog-kit/skills/" + skill + "/SKILL.md", reference]
                if not mutation
                else ["python", "C:/installed/agentic-backlog-kit/scripts/backlog.py", "sync-apply"]
            ),
            "text": "agentic-backlog-kit " + skill + " SKILL.md " + reference + " " + authorization,
        }
        events.append({"type": "item.completed", "item": item})
        events.append(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": "agentic-backlog-kit activated " + skill + " and read " + reference + " " + authorization,
                },
            }
        )
        events.append(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 60,
                    "output_tokens": 20,
                    "reasoning_output_tokens": 5,
                },
            }
        )
        return "".join(json.dumps(event) + "\n" for event in events)

    def _append_trace_manifest_item(self, cwd: str, item_id: str = "STORY-0003") -> None:
        path = Path(cwd) / ".agentic-backlog" / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if not any(item.get("id") == item_id for item in data["items"]):
            item = copy.deepcopy(next(item for item in data["items"] if item["id"] == "STORY-0002"))
            item.update({"id": item_id, "title": "Export the filtered backlog as CSV"})
            data["items"].append(item)
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def test_seed_trace_workspace_is_compact_and_hashes_each_corpus_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            workspace = self.harness.seed_trace_workspace(
                suite,
                Path(temporary) / "traces",
                case_id="follow-up-ingest-show",
                mode="mcp_unavailable",
            )
            self.assertTrue((workspace["path"] / ".agentic-backlog" / "manifest.json").is_file())
            self.assertTrue((workspace["path"] / ".agentic-backlog" / "cache" / "scaffold.json").is_file())
            self.assertEqual(2, len(workspace["prompt_sha256"]))
            self.assertTrue(workspace["before_sha256"])
            self.assertFalse(any(path.name == "SKILL.md" for path in workspace["path"].rglob("*")))
            self.assertEqual("workspace-write", workspace["sandbox"])
            self.assertIn("only persistent change", (workspace["path"] / "AGENTS.md").read_text().lower())
            self.assertFalse((workspace["path"] / ".r06-trace.json").exists())
            self.assertTrue((Path(temporary) / "traces" / workspace["metadata_path"]).is_file())

    def test_parse_trace_jsonl_redacts_paths_and_tokens_and_keeps_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            case = {
                "expected_turns": [
                    {
                        "activated": True,
                        "skill": "backlog-ingest",
                        "required_references": [
                            "skills/backlog-ingest/references/item-contract.md"
                        ],
                    }
                ]
            }
            output = self._fake_trace_output()
            output += json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": "Authorization: Bearer ghp_1234567890SECRET",
                    },
                }
            ) + "\n"
            parsed = self.harness.parse_trace_jsonl(
                output,
                "warning from C:/private/path",
                case=case,
                mode="mcp_unavailable",
                workspace=workspace,
            )
            serialized = json.dumps(parsed)
        self.assertTrue(parsed["jsonl_valid"])
        self.assertEqual(100, parsed["usage"]["input_tokens"])
        self.assertEqual(["skills/backlog-ingest/references/item-contract.md"], parsed["references"]["observed"])
        self.assertNotIn("ghp_", serialized)
        self.assertNotIn("C:/private/path", serialized)
        confirmed = self.harness.parse_trace_jsonl(
            self._fake_trace_output(
                skill="backlog-sync-github",
                reference="skills/backlog-sync-github/references/github-mapping.md",
                authorization="confirmation required; confirmed plan_digest: " + "a" * 64,
            ),
            "",
            case={
                "expected_turns": [{
                    "activated": True,
                    "skill": "backlog-sync-github",
                    "required_references": [
                        "skills/backlog-sync-github/references/github-mapping.md"
                    ],
                }]
            },
            mode="mcp_unavailable",
            workspace=workspace,
        )
        self.assertTrue(confirmed["confirmation"]["provided"])
        self.assertTrue(confirmed["confirmation"]["exact_digest_observed"])
        self.assertFalse(confirmed["mutation"]["external_contact_observed"])

    def test_parse_trace_recognizes_absolute_reference_before_path_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = self._fake_trace_output(
                reference=(
                    "C:/Users/test/.codex/plugins/cache/personal/agentic-backlog-kit/"
                    "0.1.0/skills/backlog-ingest/references/item-contract.md"
                )
            )
            parsed = self.harness.parse_trace_jsonl(
                output,
                "",
                case={"expected_turns": [{
                    "activated": True,
                    "skill": "backlog-ingest",
                    "required_references": [
                        "skills/backlog-ingest/references/item-contract.md"
                    ],
                }]},
                mode="mcp_unavailable",
                workspace=Path(temporary),
            )

        self.assertTrue(parsed["references"]["all_observed"])
        self.assertNotIn("C:/Users/test", json.dumps(parsed))

    def test_run_trace_case_preserves_prompt_hash_and_follow_up_thread(self) -> None:
        calls: list[dict] = []

        def runner(command, **kwargs):
            calls.append({"command": list(command), **kwargs})
            if "resume" not in command:
                self._append_trace_manifest_item(kwargs["cwd"])
                output = self._fake_trace_output(
                    thread_id="thread-trace-1", authorization="STORY-0003"
                )
            else:
                events = [
                    {"type": "thread.started", "thread_id": "thread-trace-1"},
                    {"type": "item.completed", "item": {
                        "type": "agent_message",
                        "text": "STORY-0003 is still an idea and is not ready for scheduling.",
                    }},
                    {"type": "turn.completed", "usage": {
                        "input_tokens": 100, "cached_input_tokens": 60,
                        "output_tokens": 20, "reasoning_output_tokens": 5,
                    }},
                ]
                output = "".join(json.dumps(event) + "\n" for event in events)
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite,
                Path(temporary) / "traces",
                case_id="follow-up-ingest-show",
                mode="mcp_unavailable",
                executable="codex.cmd",
                runner=runner,
            )
        self.assertTrue(record["passed"], record["failures"])
        self.assertEqual(2, len(calls))
        self.assertTrue(record["session"]["continuation_reused"])
        self.assertEqual(2, len(record["turns"]))
        self.assertEqual(
            [
                self.harness._prompt_hash(turn["prompt"])
                for turn in next(
                    case for case in suite["cases"] if case["id"] == "follow-up-ingest-show"
                )["turns"]
            ],
            record["prompt_sha256"],
        )
        self.assertNotIn("--ephemeral", calls[0]["command"])
        self.assertNotIn("--ephemeral", calls[1]["command"])
        self.assertEqual("workspace-write", calls[0]["command"][calls[0]["command"].index("-s") + 1])
        self.assertNotIn("-s", calls[1]["command"])
        self.assertIn("model_reasoning_effort=max", calls[0]["command"])
        self.assertEqual("workspace-write", record["commands"][1]["sandbox"])
        self.assertFalse(record["session"]["ephemeral"])
        self.assertEqual(64, len(record["commands"][1]["thread_id_sha256"]))
        self.assertNotIn("thread-trace-1", json.dumps(record))
        self.assertTrue(record["manifest"]["valid"])
        self.assertEqual("STORY-0003", record["manifest"]["stable_item_id"])
        self.assertEqual(record["manifest"]["stable_item_id"], record["manifest"]["added_item_ids"][0])
        self.assertTrue(record["turns"][1]["activation"]["inherited_from_reused_session"])
        self.assertTrue(record["turns"][1]["references"]["inherited_from_reused_session"])
        self.assertTrue(record["turns"][1]["continuity"]["identifier_reused"])
        self.assertEqual(200, record["usage"]["input_tokens"])
        self.assertEqual(40, record["usage"]["output_tokens"])
        report = self.harness.verify_trace_records(
            suite, [record], selected_cases=["follow-up-ingest-show"],
            selected_modes=["mcp_unavailable"],
        )
        self.assertTrue(report["passed"], report["failures"])

    def test_run_trace_case_rejects_follow_up_without_thread_identity(self) -> None:
        def runner(command, **kwargs):
            resumed = "resume" in command
            if not resumed:
                self._append_trace_manifest_item(kwargs["cwd"])
            return subprocess.CompletedProcess(
                command, 0,
                stdout=self._fake_trace_output(
                    thread_id=None if resumed else "thread-trace-1"
                ),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite, Path(temporary) / "traces", case_id="follow-up-ingest-show",
                mode="mcp_unavailable", executable="codex.cmd", runner=runner,
            )

        self.assertFalse(record["passed"])
        self.assertTrue(any("thread identity" in value for value in record["failures"]))

    def test_run_trace_case_never_resumes_an_incomplete_first_turn(self) -> None:
        calls: list[list[str]] = []

        def runner(command, **kwargs):
            calls.append(list(command))
            raise subprocess.TimeoutExpired(command, timeout=1, output="")

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite, Path(temporary) / "traces", case_id="follow-up-ingest-show",
                mode="mcp_unavailable", executable="codex.cmd", runner=runner,
            )

        self.assertEqual(1, len(calls))
        self.assertFalse(record["passed"])
        self.assertTrue(any("later prompts were not sent" in value for value in record["failures"]))

    def test_follow_up_requires_a_reused_result_identifier(self) -> None:
        calls = 0

        def runner(command, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                self._append_trace_manifest_item(kwargs["cwd"])
            return subprocess.CompletedProcess(
                command, 0,
                stdout=self._fake_trace_output(thread_id="thread-trace-1"),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite, Path(temporary) / "traces", case_id="follow-up-ingest-show",
                mode="mcp_unavailable", executable="codex.cmd", runner=runner,
            )

        self.assertFalse(record["passed"])
        self.assertTrue(any("identifier continuity" in value for value in record["failures"]))

    def test_default_trace_invocation_bounds_combined_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            from evals.installed_plugin import trace
            status, _, stdout, stderr, _ = trace._invoke_subprocess(
                [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1000000)"],
                Path(temporary), "", 5, 4096,
            )

        self.assertEqual("output_limit_exceeded", status)
        self.assertLessEqual(len(stdout.encode() + stderr.encode()), 4096)

    def test_trace_runner_fails_closed_on_mutation_and_malformed_jsonl(self) -> None:
        def runner(command, **kwargs):
            self._append_trace_manifest_item(kwargs["cwd"])
            output = self._fake_trace_output(mutation=True) + "not-json\n"
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite,
                Path(temporary) / "traces",
                case_id="direct-ingest",
                mode="mcp_unavailable",
                executable="codex.cmd",
                runner=runner,
            )
        self.assertFalse(record["passed"])
        self.assertTrue(any("JSONL" in failure for failure in record["failures"]))
        self.assertTrue(any("mutation" in failure for failure in record["failures"]))

    def test_trace_verifier_fails_closed_on_malformed_nested_evidence(self) -> None:
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(
                command, 0, stdout=self._fake_trace_output(), stderr=""
            )

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite, Path(temporary) / "traces", case_id="direct-ingest",
                mode="mcp_unavailable", executable="codex.cmd", runner=runner,
            )
            record["trace"]["mutation"] = "malformed"
            report = self.harness.verify_trace_records(
                suite, [record], selected_cases=["direct-ingest"],
                selected_modes=["mcp_unavailable"],
            )
        self.assertFalse(report["passed"])
        self.assertTrue(any("mutation evidence" in value for value in report["failures"]))

    def test_trace_verifier_rejects_truncated_output(self) -> None:
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(
                command, 0, stdout=self._fake_trace_output(), stderr=""
            )

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite, Path(temporary) / "traces", case_id="direct-ingest",
                mode="mcp_unavailable", executable="codex.cmd", runner=runner,
            )
            record["trace"]["output_truncated"] = True
            report = self.harness.verify_trace_records(
                suite, [record], selected_cases=["direct-ingest"],
                selected_modes=["mcp_unavailable"],
            )
        self.assertFalse(report["passed"])
        self.assertTrue(any("complete JSONL evidence" in value for value in report["failures"]))

    def test_ingestion_rejects_invalid_fixture_manifest(self) -> None:
        def runner(command, **kwargs):
            path = Path(kwargs["cwd"]) / ".agentic-backlog" / "manifest.json"
            path.write_text("{}\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                command, 0, stdout=self._fake_trace_output(), stderr=""
            )

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite, Path(temporary) / "traces", case_id="direct-ingest",
                mode="mcp_unavailable", executable="codex.cmd", runner=runner,
            )

        self.assertFalse(record["passed"])
        self.assertTrue(any("manifest validation" in value for value in record["failures"]))

    def test_trace_runner_rejects_external_tool_evidence_for_local_ingestion(self) -> None:
        def runner(command, **kwargs):
            self._append_trace_manifest_item(kwargs["cwd"])
            events = [json.loads(line) for line in self._fake_trace_output().splitlines()]
            events[1]["item"]["type"] = "mcp_tool_call"
            return subprocess.CompletedProcess(
                command, 0, stdout="".join(json.dumps(event) + "\n" for event in events), stderr=""
            )

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite, Path(temporary) / "traces", case_id="direct-ingest",
                mode="mcp_unavailable", executable="codex.cmd", runner=runner,
            )

        self.assertFalse(record["passed"])
        self.assertTrue(any("external" in value for value in record["failures"]))

    def test_trace_runner_allows_manifest_file_change_evidence_for_local_ingestion(self) -> None:
        def runner(command, **kwargs):
            self._append_trace_manifest_item(kwargs["cwd"])
            events = [json.loads(line) for line in self._fake_trace_output().splitlines()]
            reference_read = copy.deepcopy(events[1])
            events[1]["item"].update({
                "type": "file_change",
                "command": ["apply_patch", ".agentic-backlog/manifest.json"],
            })
            events.insert(1, reference_read)
            events.insert(3, {"type": "item.completed", "item": {
                "type": "command_execution",
                "command": [
                    "python", "C:/installed/agentic-backlog-kit/scripts/backlog.py",
                    "item-add", "--input", ".agentic-backlog/cache/item.json",
                ],
            }})
            return subprocess.CompletedProcess(
                command, 0, stdout="".join(json.dumps(event) + "\n" for event in events), stderr=""
            )

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite, Path(temporary) / "traces", case_id="direct-ingest",
                mode="mcp_unavailable", executable="codex.cmd", runner=runner,
            )

        self.assertTrue(record["passed"], record["failures"])
        self.assertTrue(record["trace"]["mutation"]["detected_in_events"])
        self.assertEqual([".agentic-backlog/manifest.json"], record["workspace"]["changed_paths"])
        report = self.harness.verify_trace_records(
            suite, [record], selected_cases=["direct-ingest"],
            selected_modes=["mcp_unavailable"],
        )
        self.assertTrue(report["passed"], report["failures"])

    def test_trace_runner_requires_confirmation_and_mcp_proof(self) -> None:
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=self._fake_trace_output(
                    skill="backlog-init",
                    reference="skills/backlog-init/references/scaffold.md",
                ),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite,
                Path(temporary) / "confirmation",
                case_id="direct-init",
                mode="mcp_unavailable",
                executable="codex.cmd",
                runner=runner,
            )
            blocked = self.harness.run_trace_case(
                suite,
                Path(temporary) / "catalog",
                case_id="direct-init",
                mode="mcp_available",
                executable="codex.cmd",
            )
            uncertain = self.harness.run_trace_case(
                suite,
                Path(temporary) / "uncertain-catalog",
                case_id="direct-init",
                mode="mcp_unavailable",
                executable="codex.cmd",
                catalog={"github_mcp": None},
            )

        self.assertFalse(record["passed"])
        self.assertTrue(any("confirmation" in value for value in record["failures"]))
        self.assertTrue(any("denial" in value for value in record["failures"]))
        self.assertEqual("blocked", blocked["status"])
        self.assertIn("MCP availability", blocked["failures"][0])
        self.assertEqual("blocked", uncertain["status"])
        self.assertIn("not proven", uncertain["failures"][0])

    def test_trace_runner_detects_empty_directory_mutation(self) -> None:
        def runner(command, **kwargs):
            self._append_trace_manifest_item(kwargs["cwd"])
            Path(kwargs["cwd"], "unexpected-directory").mkdir()
            return subprocess.CompletedProcess(
                command, 0, stdout=self._fake_trace_output(), stderr=""
            )

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            record = self.harness.run_trace_case(
                suite,
                Path(temporary) / "mutation",
                case_id="direct-ingest",
                mode="mcp_unavailable",
                executable="codex.cmd",
                runner=runner,
            )

        self.assertFalse(record["passed"])
        self.assertTrue(any("mutation" in value for value in record["failures"]))

    def test_run_traces_supports_selected_pairs_and_reports_full_corpus_remainder(self) -> None:
        calls: list[list[str]] = []

        def runner(command, **kwargs):
            if not calls:
                self._append_trace_manifest_item(kwargs["cwd"])
            calls.append(list(command))
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=self._fake_trace_output(),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as temporary:
            suite = self._trace_suite(temporary)
            summary = self.harness.run_traces(
                suite,
                Path(temporary) / "traces",
                case_ids=["direct-ingest"],
                modes=["mcp_unavailable"],
                executable="codex.cmd",
                runner=runner,
            )
            records = self.harness.load_results(Path(temporary) / "traces" / "trace-results.ndjson")
        self.assertTrue(summary["passed"])
        self.assertEqual(1, summary["record_count"])
        self.assertEqual(1, len(records))
        self.assertEqual(33, len(summary["remaining_full_corpus_pairs"]))
        report = self.harness.verify_trace_records(
            suite,
            records,
            selected_cases=["direct-ingest"],
            selected_modes=["mcp_unavailable"],
        )
        self.assertTrue(report["passed"], report["failures"])

    def test_write_trace_records_refuses_unredacted_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(self.harness.EvaluationError):
                self.harness.write_trace_records(
                    Path(temporary) / "trace.ndjson",
                    [{"case_id": "direct-ingest", "secret": "ghp_1234567890SECRET"}],
                )


if __name__ == "__main__":
    unittest.main()
