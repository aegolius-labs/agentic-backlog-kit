"""S-R29-2: GitHub's read-after-write lag is re-read, not reported as drift."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from agentic_backlog_kit.api_benchmark import SimulatedGitHub
from agentic_backlog_kit.cli import main
from agentic_backlog_kit.github import GitHubPlanExecutor, GitHubService
from agentic_backlog_kit.snapshot import GitHubSnapshotReader
from agentic_backlog_kit.sync import build_sync_plan
from agentic_backlog_kit.verification import verify_delays, verify_sync_apply

from tests.helpers import item, manifest


def _reader(github: SimulatedGitHub) -> GitHubSnapshotReader:
    return GitHubSnapshotReader(
        github, owner="aegolius-labs", repository="example", project_number=1
    )


def _applied(data: dict) -> tuple[object, dict, dict]:
    """Apply a cold plan to a simulated repository; return plan, before and after."""

    github = SimulatedGitHub(data)
    before = _reader(github).read()
    plan = build_sync_plan(data, before)
    executor = GitHubPlanExecutor(
        GitHubService(
            github, owner="aegolius-labs", repository="example", project_number=1
        ),
        remote_snapshot=before,
    )
    for action in plan.actions:
        executor(action)
    return plan, before, _reader(github).read()


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def _verify(plan, data, reads, *, window=60.0):
    clock = FakeClock()
    sequence = list(reads)

    def read():
        return sequence.pop(0) if len(sequence) > 1 else sequence[0]

    result = verify_sync_apply(
        plan, data, read, window=window, sleep=clock.sleep, clock=clock
    )
    return result, clock


class VerifyDelaysTests(unittest.TestCase):
    def test_delays_double_from_two_seconds_and_fill_the_window(self) -> None:
        self.assertEqual([2, 4, 8, 16, 30], verify_delays(60))
        self.assertEqual([2, 1], verify_delays(3))
        self.assertEqual([], verify_delays(0))

    def test_a_negative_window_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            verify_delays(-1)


class PostApplyVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = manifest(item("T-1"), item("T-2", depends_on=["T-1"]))
        self.plan, self.before, self.after = _applied(self.data)

    def test_a_converged_read_is_verified_at_once(self) -> None:
        result, clock = _verify(self.plan, self.data, [self.after])

        self.assertEqual("converged", result.status)
        self.assertFalse(result.lag_observed)
        self.assertEqual(1, result.reads)
        self.assertEqual(0.0, result.convergence_seconds)
        self.assertEqual([], clock.sleeps)

    def test_residuals_repeating_the_apply_are_re_read_until_they_converge(self) -> None:
        result, clock = _verify(
            self.plan, self.data, [self.before, self.before, self.after]
        )

        self.assertEqual("converged", result.status)
        self.assertTrue(result.lag_observed)
        self.assertEqual(3, result.reads)
        self.assertEqual([2, 4], clock.sleeps)
        self.assertEqual(6.0, result.convergence_seconds)
        self.assertEqual([], result.drift_actions)

    def test_lag_that_outlasts_the_window_is_drift(self) -> None:
        result, clock = _verify(self.plan, self.data, [self.before], window=10)

        self.assertEqual("drift", result.status)
        self.assertTrue(result.lag_observed)
        self.assertEqual(4, result.reads)
        self.assertEqual([2, 4, 4], clock.sleeps)
        self.assertIsNone(result.convergence_seconds)
        self.assertEqual(
            sorted(action.as_dict()["kind"] for action in self.plan.actions),
            sorted(action["kind"] for action in result.drift_actions),
        )

    def test_a_residual_the_apply_did_not_write_is_drift_without_waiting(self) -> None:
        changed = manifest(
            item("T-1", title="Renamed after apply"), item("T-2", depends_on=["T-1"])
        )

        result, clock = _verify(self.plan, changed, [self.after])

        self.assertEqual("drift", result.status)
        self.assertFalse(result.lag_observed)
        self.assertEqual(1, result.reads)
        self.assertEqual([], clock.sleeps)
        self.assertEqual(["issue.update"], [a["kind"] for a in result.drift_actions])

    def test_a_dependency_on_a_different_blocker_is_not_lag(self) -> None:
        data = manifest(item("T-1"), item("T-2"), item("T-3", depends_on=["T-1"]))
        plan, _, after = _applied(data)
        moved = manifest(item("T-1"), item("T-2"), item("T-3", depends_on=["T-1", "T-2"]))

        result, clock = _verify(plan, moved, [after])

        self.assertEqual("drift", result.status)
        self.assertFalse(result.lag_observed)
        self.assertEqual([], clock.sleeps)
        self.assertIn(
            ("issue.add_dependency", "T-3", {"depends_on": "T-2"}),
            [(a["kind"], a["item_id"], a["payload"]) for a in result.drift_actions],
        )


class LaggingGitHub(SimulatedGitHub):
    """Hides every issue from the listing for the first ``lag_reads`` listings."""

    def __init__(self, manifest_data: dict, lag_reads: int) -> None:
        super().__init__(manifest_data)
        self.lag_reads = lag_reads
        self.hidden = False

    def rest(self, method, path, payload=None):
        if method == "GET" and "/issues?" in path and self.hidden and self.lag_reads:
            self.rest_calls += 1
            self.lag_reads -= 1
            return []
        if method == "POST" and path.endswith("/issues"):
            self.hidden = True
        return super().rest(method, path, payload)


class SyncApplyVerificationCliTests(unittest.TestCase):
    def _sync_apply(self, github: SimulatedGitHub, data: dict, *extra: str) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            plan_path = root / "plan.json"
            receipt_path = root / "receipt.json"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            plan = build_sync_plan(data, _reader(github).read())
            plan_path.write_text(json.dumps(plan.as_dict()), encoding="utf-8")
            with (
                patch("agentic_backlog_kit.cli._transport", return_value=github),
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
                        *extra,
                    ]
                )
            return result, json.loads(receipt_path.read_text(encoding="utf-8"))

    def test_lag_past_the_window_fails_and_the_receipt_records_it(self) -> None:
        data = manifest(item("T-1"))

        result, receipt = self._sync_apply(
            LaggingGitHub(data, lag_reads=5), data, "--verify-window", "0"
        )

        self.assertEqual(1, result)
        self.assertEqual("completed", receipt["status"])
        self.assertEqual("drift", receipt["verification"]["status"])
        self.assertTrue(receipt["verification"]["lag_observed"])
        self.assertIsNone(receipt["verification"]["convergence_seconds"])


if __name__ == "__main__":
    unittest.main()
