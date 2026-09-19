from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr

from agentic_backlog_kit import cli
from agentic_backlog_kit.execution import describe_failure, failure_hint
from agentic_backlog_kit.github import GitHubApiError
from agentic_backlog_kit.scaffold import ScaffoldAction, ScaffoldPlan


class FailureHintTests(unittest.TestCase):
    """R22 - a rejected write must name its likely cause."""

    def test_names_an_unavailable_native_issue_type(self) -> None:
        hint = failure_hint(
            "issue.create",
            {"type": "Story", "fallback_label": "type:story"},
            GitHubApiError(422, "Validation Failed"),
        )

        self.assertIn("Story", hint)
        self.assertIn("issue_type_mode", hint)
        self.assertIn("type:story", hint)

    def test_names_a_permission_failure(self) -> None:
        hint = failure_hint(
            "project.field.create", {}, GitHubApiError(403, "Forbidden")
        )

        self.assertIn("permission", hint)

    def test_names_a_rate_limit(self) -> None:
        hint = failure_hint(
            "issue.create", {}, GitHubApiError(429, "API rate limit exceeded")
        )

        self.assertIn("rate-limited", hint)

    def test_names_stale_state(self) -> None:
        hint = failure_hint("issue.update", {}, GitHubApiError(404, "Not Found"))

        self.assertIn("Rebuild the plan", hint)

    def test_stays_silent_rather_than_guessing(self) -> None:
        self.assertIsNone(
            failure_hint("issue.create", {}, GitHubApiError(500, "Server Error"))
        )

    def test_does_not_blame_the_issue_type_without_one(self) -> None:
        hint = failure_hint("issue.create", {}, GitHubApiError(422, "Validation Failed"))

        self.assertIsNone(hint)

    def test_describes_the_failing_action_with_its_item(self) -> None:
        described = describe_failure(
            {"kind": "issue.create", "item_id": "S-R11-1"},
            GitHubApiError(422, "Validation Failed"),
            "Set issue_type_mode to 'labels'.",
        )

        self.assertIn("issue.create", described)
        self.assertIn("S-R11-1", described)
        self.assertIn("issue_type_mode", described)


class CliErrorReportingTests(unittest.TestCase):
    """R22 - the operator sees a decision, not a stack trace."""

    def test_a_rejected_command_prints_structured_json_and_exits_one(self) -> None:
        stderr = io.StringIO()

        with redirect_stderr(stderr):
            code = cli.main(
                ["init", "--owner", "", "--repository", "x", "--project-number", "1"]
            )

        self.assertEqual(1, code)
        payload = json.loads(stderr.getvalue())
        self.assertIn("error", payload)
        self.assertIn("message", payload)


class ScaffoldConvergenceTests(unittest.TestCase):
    """R23 - a completed apply must not imply a converged target."""

    def _plan(self, *actions: ScaffoldAction) -> ScaffoldPlan:
        return ScaffoldPlan(
            actions=list(actions),
            digest="d" * 64,
            manifest_fingerprint="m" * 64,
            snapshot_fingerprint="s" * 64,
        )

    def test_a_created_view_declares_the_follow_up(self) -> None:
        plan = self._plan(
            ScaffoldAction("project.view.create", {"name": "Backlog"}, {"view": None})
        )

        self.assertIsNotNone(plan.follow_up)
        self.assertIn("follow-up scaffold plan", plan.follow_up)
        self.assertFalse(plan.as_dict()["converges_in_one_apply"])

    def test_a_plan_without_view_creation_converges(self) -> None:
        plan = self._plan(
            ScaffoldAction("project.field.create", {"name": "Impact"}, {"field": None})
        )

        self.assertIsNone(plan.follow_up)
        self.assertTrue(plan.as_dict()["converges_in_one_apply"])

    def test_an_empty_plan_converges(self) -> None:
        plan = self._plan()

        self.assertTrue(plan.as_dict()["converges_in_one_apply"])

    def test_the_follow_up_reaches_the_plan_payload(self) -> None:
        plan = self._plan(
            ScaffoldAction("project.view.create", {"name": "Kanban"}, {"view": None})
        )

        self.assertEqual(plan.follow_up, plan.as_dict()["follow_up"])


if __name__ == "__main__":
    unittest.main()
