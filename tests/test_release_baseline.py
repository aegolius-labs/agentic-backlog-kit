from __future__ import annotations

import unittest

from scripts.release_baseline import (
    ReleaseBaselineError,
    evaluate_baseline,
    find_baseline,
)


class FindBaselineTests(unittest.TestCase):
    def test_finds_the_highest_version_tag(self) -> None:
        self.assertEqual("v0.5.0", find_baseline(["v0.1.0", "v0.5.0", "v0.4.0"]))

    def test_orders_numerically_rather_than_lexically(self) -> None:
        self.assertEqual("v0.10.0", find_baseline(["v0.9.0", "v0.10.0"]))

    def test_ignores_tags_that_are_not_versions(self) -> None:
        self.assertEqual(
            "v0.1.0", find_baseline(["nightly", "release-candidate", "v0.1.0"])
        )

    def test_ignores_a_prerelease_or_suffixed_tag(self) -> None:
        self.assertIsNone(find_baseline(["v1.0.0-rc1", "v1.0.0+build"]))

    def test_returns_none_without_any_version_tag(self) -> None:
        self.assertIsNone(find_baseline([]))
        self.assertIsNone(find_baseline(["main", "v1", "1.0.0"]))


class EvaluateBaselineTests(unittest.TestCase):
    """R14-F7 - an absent new tag must be explained, not assumed benign."""

    def test_a_real_release_passes_regardless_of_history(self) -> None:
        report = evaluate_baseline([], new_tag="v0.1.0")

        self.assertTrue(report.released)
        self.assertIn("Releasing v0.1.0", report.reason)

    def test_a_no_bump_with_a_baseline_is_a_legitimate_no_op(self) -> None:
        report = evaluate_baseline(["v0.4.0", "v0.5.0"], new_tag="")

        self.assertFalse(report.released)
        self.assertEqual("v0.5.0", report.baseline)
        self.assertIn("nothing to publish", report.reason)

    def test_a_no_bump_without_a_baseline_fails(self) -> None:
        with self.assertRaises(ReleaseBaselineError) as raised:
            evaluate_baseline([], new_tag="")

        self.assertIn("No release baseline exists", str(raised.exception))

    def test_the_failure_explains_how_to_create_the_baseline(self) -> None:
        with self.assertRaises(ReleaseBaselineError) as raised:
            evaluate_baseline(["nightly"], new_tag="")

        message = str(raised.exception)
        self.assertIn("git tag", message)
        self.assertIn("never creates a tag", message)

    def test_a_none_new_tag_is_treated_as_a_no_bump(self) -> None:
        with self.assertRaises(ReleaseBaselineError):
            evaluate_baseline([], new_tag=None)

    def test_non_version_tags_do_not_count_as_a_baseline(self) -> None:
        with self.assertRaises(ReleaseBaselineError):
            evaluate_baseline(["v1", "1.0.0", "latest"], new_tag="")


class GuardContractTests(unittest.TestCase):
    """The guard must not be removable without the contract noticing."""

    def setUp(self) -> None:
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        self.example = json.loads(
            (
                root / "tests/fixtures/organization-release/contract-example.json"
            ).read_text(encoding="utf-8")
        )

    def _validate(self) -> None:
        from scripts.release_contract import validate_contract

        validate_contract(
            *(self.example[name] for name in ("caller", "compute", "publisher"))
        )

    def test_accepts_the_guarded_caller(self) -> None:
        self._validate()

    def test_rejects_removing_the_guard(self) -> None:
        from scripts.release_contract import ContractError

        del self.example["caller"]["jobs"]["baseline-guard"]

        with self.assertRaisesRegex(ContractError, "drops the release baseline guard"):
            self._validate()

    def test_rejects_a_guard_that_never_runs(self) -> None:
        from scripts.release_contract import ContractError

        self.example["caller"]["jobs"]["baseline-guard"]["if"] = (
            "${{ needs.compute-version.outputs.new-tag != '' }}"
        )

        with self.assertRaisesRegex(ContractError, "no-bump path"):
            self._validate()

    def test_rejects_a_guard_that_can_write(self) -> None:
        from scripts.release_contract import ContractError

        self.example["caller"]["jobs"]["baseline-guard"]["permissions"] = {
            "contents": "write"
        }

        with self.assertRaisesRegex(ContractError, "read-only"):
            self._validate()

    def test_rejects_a_guard_that_creates_the_baseline(self) -> None:
        from scripts.release_contract import ContractError

        self.example["caller"]["jobs"]["baseline-guard"]["steps"][-1]["run"] = (
            "git tag -a v0.0.0 && python scripts/release_baseline.py"
        )

        with self.assertRaisesRegex(ContractError, "may create a tag"):
            self._validate()

    def test_rejects_a_shallow_guard_checkout(self) -> None:
        from scripts.release_contract import ContractError

        checkout = self.example["caller"]["jobs"]["baseline-guard"]["steps"][0]
        checkout["with"]["fetch-depth"] = 1

        with self.assertRaisesRegex(ContractError, "truncates tag history"):
            self._validate()

    def test_rejects_dropping_the_baseline_check_itself(self) -> None:
        from scripts.release_contract import ContractError

        self.example["caller"]["jobs"]["baseline-guard"]["steps"][-1]["run"] = (
            "echo skipped"
        )

        with self.assertRaisesRegex(ContractError, "does not run the baseline check"):
            self._validate()


if __name__ == "__main__":
    unittest.main()
