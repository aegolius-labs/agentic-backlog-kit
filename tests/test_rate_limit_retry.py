"""S-R28-2: a throttled request waits as GitHub asks, within a bounded budget."""

from __future__ import annotations

import io
import json
import unittest
from email.message import Message
from subprocess import CompletedProcess
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from agentic_backlog_kit.execution import failure_hint
from agentic_backlog_kit.github import (
    SECONDARY_RATE_LIMIT_WAIT,
    GitHubApiError,
    GitHubCliTransport,
    GitHubHttpTransport,
    RateLimitBudget,
    rate_limit_wait,
)


NOW = 1_800_000_000.0
SECONDARY = "You have exceeded a secondary rate limit. Please wait a few minutes."


class RecordingBudget(RateLimitBudget):
    """A budget that records its waits instead of sleeping through them."""

    def __init__(self, **kwargs) -> None:
        self.slept: list[float] = []
        super().__init__(
            sleep=self.slept.append, clock=lambda: NOW, report=lambda _: None, **kwargs
        )


def _headers(values: dict[str, str]) -> Message:
    message = Message()
    for name, value in values.items():
        message[name] = value
    return message


def _http_error(status: int, message: str, headers: dict[str, str] | None = None) -> HTTPError:
    body = io.BytesIO(json.dumps({"message": message}).encode())
    return HTTPError("u", status, message, _headers(headers or {}), body)


def _ok(payload: dict, headers: dict[str, str] | None = None) -> io.BytesIO:
    stream = io.BytesIO(json.dumps(payload).encode())
    stream.status = 200
    stream.headers = _headers(headers or {})
    return stream


def _included(status: str, headers: dict[str, str], body: str) -> str:
    lines = [f"HTTP/2.0 {status}", *(f"{name}: {value}" for name, value in headers.items())]
    return "\n".join(lines) + "\n\n" + body


class WaitTests(unittest.TestCase):
    def test_retry_after_is_honoured(self) -> None:
        error = GitHubApiError(429, "slow down", headers={"Retry-After": "7"})

        self.assertEqual(7.0, rate_limit_wait(error, NOW, 0))

    def test_an_exhausted_primary_limit_waits_for_its_reset(self) -> None:
        error = GitHubApiError(
            403,
            "API rate limit exceeded for user ID 1.",
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(NOW) + 42)},
        )

        self.assertEqual(43.0, rate_limit_wait(error, NOW, 0))

    def test_a_secondary_limit_without_a_header_backs_off_exponentially(self) -> None:
        error = GitHubApiError(403, SECONDARY)

        self.assertEqual(
            [SECONDARY_RATE_LIMIT_WAIT, 2 * SECONDARY_RATE_LIMIT_WAIT],
            [rate_limit_wait(error, NOW, 0), rate_limit_wait(error, NOW, 1)],
        )

    def test_a_permission_403_is_not_a_rate_limit(self) -> None:
        error = GitHubApiError(
            403, "Resource not accessible by integration", headers={"X-RateLimit-Remaining": "4000"}
        )

        self.assertIsNone(rate_limit_wait(error, NOW, 0))

    def test_failures_with_an_unknown_outcome_are_not_rate_limits(self) -> None:
        for error in (GitHubApiError(500, "Server Error"), GitHubApiError(0, "timed out")):
            with self.subTest(status=error.status):
                self.assertIsNone(rate_limit_wait(error, NOW, 0))


class BudgetTests(unittest.TestCase):
    def test_a_refused_request_is_retried_after_the_wait(self) -> None:
        budget = RecordingBudget()
        responses = [GitHubApiError(429, "slow", headers={"Retry-After": "5"}), "done"]

        def send():
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        self.assertEqual("done", budget.call(send))
        self.assertEqual([5.0], budget.slept)

    def test_a_wait_beyond_the_budget_is_not_started(self) -> None:
        budget = RecordingBudget(max_total_wait=60)
        calls = []

        def send():
            calls.append(1)
            raise GitHubApiError(429, "slow", headers={"Retry-After": "61"})

        with self.assertRaises(GitHubApiError):
            budget.call(send)
        self.assertEqual([], budget.slept)
        self.assertEqual(1, len(calls))

    def test_the_budget_is_shared_across_requests_in_one_run(self) -> None:
        budget = RecordingBudget(max_total_wait=100)
        state = {"refusals": 0}

        def refused_once():
            if state["refusals"] < 1:
                state["refusals"] += 1
                raise GitHubApiError(429, "slow", headers={"Retry-After": "60"})
            return "ok"

        budget.call(refused_once)
        state["refusals"] = 0
        # 60 already spent; another 60 would cross 100, so the second fails.
        with self.assertRaises(GitHubApiError):
            budget.call(refused_once)
        self.assertEqual([60.0], budget.slept)

    def test_attempts_are_bounded_even_when_waits_are_short(self) -> None:
        budget = RecordingBudget(max_attempts=3)
        calls = []

        def send():
            calls.append(1)
            raise GitHubApiError(429, "slow", headers={"Retry-After": "1"})

        with self.assertRaises(GitHubApiError):
            budget.call(send)
        self.assertEqual(3, len(calls))
        self.assertEqual([1.0, 1.0], budget.slept)

    def test_an_unknown_outcome_is_never_repeated(self) -> None:
        for error in (GitHubApiError(500, "Server Error"), GitHubApiError(0, "timed out")):
            with self.subTest(status=error.status):
                budget = RecordingBudget()
                calls = []

                def send(error=error):
                    calls.append(1)
                    raise error

                with self.assertRaises(GitHubApiError):
                    budget.call(send)
                self.assertEqual(1, len(calls))
                self.assertEqual([], budget.slept)

    def test_an_exhausted_budget_fails_with_the_existing_hint(self) -> None:
        # A secondary limit arrives as a 403; the hint must not blame scopes.
        budget = RecordingBudget(max_total_wait=0)

        def send():
            raise GitHubApiError(403, SECONDARY)

        with self.assertRaises(GitHubApiError) as raised:
            budget.call(send)
        hint = failure_hint("issue.create", {}, raised.exception)
        self.assertIn("rate-limited", hint)
        self.assertNotIn("permission", hint)


class HttpTransportTests(unittest.TestCase):
    def _transport(self, responses: list) -> tuple[GitHubHttpTransport, RecordingBudget, list]:
        budget = RecordingBudget()
        sent: list = []

        def urlopen(request, timeout=None):
            sent.append((request.get_method(), request.full_url))
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        self.patcher = patch("agentic_backlog_kit.github.urlopen", side_effect=urlopen)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        return GitHubHttpTransport("token", rate_limit=budget), budget, sent

    def test_a_write_refused_by_a_rate_limit_is_resent_after_the_wait(self) -> None:
        transport, budget, sent = self._transport(
            [_http_error(429, "slow", {"Retry-After": "9"}), _ok({"number": 1})]
        )

        self.assertEqual({"number": 1}, transport.rest("POST", "/repos/o/r/issues", {"title": "t"}))
        self.assertEqual(2, len(sent))
        self.assertEqual([9.0], budget.slept)

    def test_a_timed_out_write_is_not_resent(self) -> None:
        transport, budget, sent = self._transport([URLError("timed out"), _ok({})])

        with self.assertRaises(GitHubApiError):
            transport.rest("POST", "/repos/o/r/issues", {"title": "t"})
        self.assertEqual(1, len(sent))
        self.assertEqual([], budget.slept)

    def test_a_graphql_point_limit_is_retried_only_when_nothing_ran(self) -> None:
        limited = {"data": None, "errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]}
        reset = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(NOW) + 4)}
        transport, budget, sent = self._transport(
            [_ok(limited, reset), _ok({"data": {"viewer": {"login": "x"}}})]
        )

        self.assertEqual({"viewer": {"login": "x"}}, transport.graphql("query { viewer { login } }", {}))
        self.assertEqual([5.0], budget.slept)

    def test_a_partial_graphql_result_is_not_retried(self) -> None:
        partial = {
            "data": {"a": {"id": "1"}},
            "errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}],
        }
        transport, budget, sent = self._transport([_ok(partial), _ok({"data": {}})])

        with self.assertRaises(GitHubApiError):
            transport.graphql("mutation { a }", {})
        self.assertEqual(1, len(sent))


class CliTransportTests(unittest.TestCase):
    def _run(self, responses: list[CompletedProcess]):
        commands: list[list[str]] = []

        def run(command, **kwargs):
            commands.append(command)
            return responses.pop(0)

        return run, commands

    def test_the_cli_route_asks_gh_for_headers(self) -> None:
        run, commands = self._run([CompletedProcess(["gh"], 0, stdout="{}")])
        with patch("agentic_backlog_kit.github.subprocess.run", side_effect=run):
            GitHubCliTransport("gh", rate_limit=RecordingBudget()).rest("GET", "/rate_limit")

        self.assertIn("--include", commands[0])

    def test_a_secondary_limit_on_the_cli_route_waits_as_told(self) -> None:
        refused = CompletedProcess(
            ["gh"],
            1,
            stdout=_included("403 Forbidden", {"Retry-After": "30"}, json.dumps({"message": SECONDARY})),
            stderr=f"gh: {SECONDARY} (HTTP 403)",
        )
        accepted = CompletedProcess(
            ["gh"], 0, stdout=_included("201 Created", {"Content-Type": "application/json"}, '{"number": 3}')
        )
        run, commands = self._run([refused, accepted])
        budget = RecordingBudget()

        with patch("agentic_backlog_kit.github.subprocess.run", side_effect=run):
            result = GitHubCliTransport("gh", rate_limit=budget).rest(
                "POST", "/repos/o/r/issues", {"title": "t"}
            )

        self.assertEqual({"number": 3}, result)
        self.assertEqual(2, len(commands))
        self.assertEqual([30.0], budget.slept)

    def test_the_status_line_stands_in_when_stderr_names_no_status(self) -> None:
        refused = CompletedProcess(
            ["gh"],
            1,
            stdout=_included("429 Too Many Requests", {"Retry-After": "2"}, "slow down"),
            stderr="gh: HTTP 429",
        )
        run, commands = self._run([refused, CompletedProcess(["gh"], 0, stdout="{}")])
        budget = RecordingBudget()

        with patch("agentic_backlog_kit.github.subprocess.run", side_effect=run):
            GitHubCliTransport("gh", rate_limit=budget).rest("GET", "/repos/o/r")

        self.assertEqual(2, len(commands))
        self.assertEqual([2.0], budget.slept)

    def test_a_permission_failure_on_the_cli_route_is_not_retried(self) -> None:
        denied = CompletedProcess(
            ["gh"],
            1,
            stdout=_included("403 Forbidden", {"X-RateLimit-Remaining": "4999"}, "{}"),
            stderr="gh: Resource not accessible by integration (HTTP 403)",
        )
        run, commands = self._run([denied])
        budget = RecordingBudget()

        with patch("agentic_backlog_kit.github.subprocess.run", side_effect=run):
            with self.assertRaises(GitHubApiError) as raised:
                GitHubCliTransport("gh", rate_limit=budget).rest("PATCH", "/repos/o/r/issues/1", {})

        self.assertEqual(403, raised.exception.status)
        self.assertEqual(1, len(commands))
        self.assertEqual([], budget.slept)

    def test_an_empty_included_body_reads_as_empty(self) -> None:
        run, _ = self._run([CompletedProcess(["gh"], 0, stdout=_included("204 No Content", {"Server": "github.com"}, ""))])
        with patch("agentic_backlog_kit.github.subprocess.run", side_effect=run):
            result = GitHubCliTransport("gh", rate_limit=RecordingBudget()).rest(
                "DELETE", "/repos/o/r/issues/1/labels/x"
            )

        self.assertEqual({}, result)

    def test_both_routes_wait_the_same_for_the_same_refusal(self) -> None:
        reset = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(NOW) + 20)}
        message = "API rate limit exceeded for user ID 1."

        cli_budget = RecordingBudget()
        run, _ = self._run(
            [
                CompletedProcess(
                    ["gh"], 1, stdout=_included("403 Forbidden", reset, "{}"), stderr=f"gh: {message} (HTTP 403)"
                ),
                CompletedProcess(["gh"], 0, stdout="{}"),
            ]
        )
        with patch("agentic_backlog_kit.github.subprocess.run", side_effect=run):
            GitHubCliTransport("gh", rate_limit=cli_budget).rest("GET", "/repos/o/r")

        api_budget = RecordingBudget()
        responses = [_http_error(403, message, reset), _ok({})]

        def urlopen(request, timeout=None):
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch("agentic_backlog_kit.github.urlopen", side_effect=urlopen):
            GitHubHttpTransport("token", rate_limit=api_budget).rest("GET", "/repos/o/r")

        self.assertEqual([21.0], cli_budget.slept)
        self.assertEqual(cli_budget.slept, api_budget.slept)


if __name__ == "__main__":
    unittest.main()
