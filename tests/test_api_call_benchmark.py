"""S-R28-3: snapshot, plan and apply have API-call budgets enforced like byte budgets."""

from __future__ import annotations

import unittest

from agentic_backlog_kit.api_benchmark import (
    API_CALL_PHASES,
    API_CALL_SIZES,
    SimulatedGitHub,
    api_call_budget,
    assert_api_call_budgets,
    measure_api_calls,
)
from agentic_backlog_kit.benchmark import (
    assert_budgets,
    benchmark,
    representative_manifest,
)


class ApiCallBenchmarkTests(unittest.TestCase):
    def test_release_sizes_are_100_1000_and_5000_issues(self) -> None:
        self.assertEqual((100, 1_000, 5_000), API_CALL_SIZES)

    def test_measurement_is_repeatable_and_reports_every_phase(self) -> None:
        first = measure_api_calls(representative_manifest(100))
        second = measure_api_calls(representative_manifest(100))

        self.assertEqual(first, second)
        self.assertEqual(set(API_CALL_PHASES), set(first["phases"]))
        for counts in first["phases"].values():
            self.assertEqual(counts["rest"] + counts["graphql"], counts["total"])

    def test_planning_makes_no_calls_and_converged_apply_only_refreshes(self) -> None:
        phases = measure_api_calls(representative_manifest(100))["phases"]

        self.assertEqual(0, phases["plan"]["total"])
        self.assertEqual(phases["snapshot"], phases["apply"])

    def test_reads_grow_with_pages_not_issues(self) -> None:
        small = measure_api_calls(representative_manifest(100))["phases"]["snapshot"]
        large = measure_api_calls(representative_manifest(1_000))["phases"]["snapshot"]

        # Ten times the issues costs about ten times the pages, and far fewer
        # calls than one per issue.
        self.assertLess(large["total"], 1_000 // 10)
        self.assertLessEqual(large["total"], 10 * small["total"])

    def test_cold_apply_writes_every_action(self) -> None:
        result = measure_api_calls(representative_manifest(100))

        self.assertGreaterEqual(result["phases"]["cold-apply"]["total"], result["cold_actions"])

    def test_one_extra_call_per_issue_breaks_every_scaling_budget(self) -> None:
        # The release-size budgets themselves are checked by
        # BenchmarkTests.test_default_budgets_hold_for_all_release_sizes, which
        # runs the full default report.
        run = measure_api_calls(representative_manifest(100))
        for phase in ("snapshot", "apply", "cold-apply"):
            counts = run["phases"][phase]
            inflated = {
                "issues": run["issues"],
                "phases": {
                    **run["phases"],
                    phase: {**counts, "total": counts["total"] + run["issues"]},
                },
            }
            failures = assert_api_call_budgets([inflated])
            self.assertEqual(1, len(failures), phase)
            self.assertIn(f"{phase}: ", failures[0])
            self.assertIn("API calls exceeds", failures[0])

    def test_benchmark_check_fails_on_an_api_call_regression(self) -> None:
        result = benchmark((100,), (100,))
        self.assertTrue(result["within_budget"])
        result["api_call_runs"][0]["phases"]["plan"]["total"] = 1

        self.assertEqual(
            ["100 issues plan: 1 API calls exceeds 0"], assert_budgets(result)
        )

    def test_unknown_phase_has_no_budget(self) -> None:
        with self.assertRaises(ValueError):
            api_call_budget("delete", 100)

    def test_simulator_rejects_requests_it_does_not_model(self) -> None:
        transport = SimulatedGitHub(representative_manifest(100))

        with self.assertRaises(AssertionError):
            transport.rest("DELETE", "/repos/aegolius-labs/benchmark/issues/1")
        with self.assertRaises(AssertionError):
            transport.graphql("query Unknown { viewer { login } }", {})


if __name__ == "__main__":
    unittest.main()
