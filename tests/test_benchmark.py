from __future__ import annotations

import unittest

from agentic_backlog_kit.benchmark import (
    BACKLOG_SIZES,
    OPERATIONS,
    assert_budgets,
    benchmark,
    budget_for,
    representative_manifest,
    representative_snapshot,
    serialize_json,
)


class BenchmarkTests(unittest.TestCase):
    def test_representative_manifest_is_deterministic_and_valid(self) -> None:
        first = representative_manifest(100)
        second = representative_manifest(100)

        self.assertEqual(first, second)
        self.assertEqual(100, len(first["items"]))
        self.assertEqual("T-00001", first["items"][0]["id"])
        self.assertEqual("T-00100", first["items"][-1]["id"])

    def test_snapshot_matches_the_generated_backlog(self) -> None:
        data = representative_manifest(100)
        snapshot = representative_snapshot(data)

        self.assertEqual(1, snapshot["schema_version"])
        self.assertEqual(100, len(snapshot["issues"]))
        self.assertEqual(
            {item["id"] for item in data["items"]},
            {issue["abk_id"] for issue in snapshot["issues"]},
        )

    def test_benchmark_covers_each_operation_and_is_repeatable(self) -> None:
        first = benchmark((100,))
        second = benchmark((100,))

        self.assertEqual(first, second)
        self.assertEqual([100], first["sizes"])
        self.assertEqual(set(OPERATIONS), set(first["runs"][0]["measurements"]))
        for measurement in first["runs"][0]["measurements"].values():
            self.assertGreater(measurement["bytes"], 0)
            self.assertGreaterEqual(measurement["estimated_tokens"], 1)

    def test_default_sizes_include_the_three_release_targets(self) -> None:
        self.assertEqual((100, 1_000, 10_000), BACKLOG_SIZES)

    def test_default_budgets_hold_for_all_release_sizes(self) -> None:
        result = benchmark(BACKLOG_SIZES)
        self.assertEqual([], assert_budgets(result))
        self.assertTrue(result["within_budget"])

    def test_serializer_is_utf8_and_ends_with_one_newline(self) -> None:
        self.assertEqual(b'{"message":"caf\xc3\xa9"}\n', serialize_json({"message": "café"}))

    def test_budget_check_reports_byte_and_token_regressions(self) -> None:
        result = benchmark((100,))
        measurement = result["runs"][0]["measurements"]["summary"]
        budget = budget_for("summary", 100)
        measurement["bytes"] = budget["max_bytes"] + 1
        measurement["estimated_tokens"] = budget["max_estimated_tokens"] + 1

        failures = assert_budgets(result)

        self.assertEqual(2, len(failures))
        self.assertIn("bytes exceeds", failures[0])
        self.assertIn("estimated tokens exceeds", failures[1])


if __name__ == "__main__":
    unittest.main()
