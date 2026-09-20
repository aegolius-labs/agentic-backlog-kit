from __future__ import annotations

import io
import json
import unittest
from subprocess import CompletedProcess
from unittest.mock import patch
from urllib.error import HTTPError

from agentic_backlog_kit.capabilities import (
    ACTION_CAPABILITIES,
    ALL_CAPABILITIES,
    CapabilityError,
    inspect_route,
    provided_capabilities,
    require_capabilities,
    required_capabilities,
    route_name,
)
from agentic_backlog_kit.github import (
    GitHubCliTransport,
    GitHubHttpTransport,
    GitHubService,
)


class _Incomplete:
    """A route that can write issues but exposes no Projects surface.

    This is the shape Wave C actually observed in the installed generic GitHub
    MCP, which is why it is the fixture rather than an invented one.
    """

    route = "generic-mcp"
    capabilities = frozenset({"issue.write"})


class CapabilityModelTests(unittest.TestCase):
    def test_every_action_kind_declares_its_capabilities(self) -> None:
        for kind, needed in ACTION_CAPABILITIES.items():
            with self.subTest(kind=kind):
                self.assertTrue(needed)
                self.assertTrue(needed <= ALL_CAPABILITIES)

    def test_both_native_routes_are_peers(self) -> None:
        cli = GitHubCliTransport("gh")
        api = GitHubHttpTransport("token")

        self.assertEqual(provided_capabilities(cli), provided_capabilities(api))
        self.assertEqual({"gh", "api"}, {route_name(cli), route_name(api)})

    def test_an_unknown_transport_is_assumed_complete(self) -> None:
        self.assertEqual(ALL_CAPABILITIES, provided_capabilities(object()))

    def test_required_capabilities_reports_unknown_kinds(self) -> None:
        required, unknown = required_capabilities(["issue.create", "issue.explode"])

        self.assertIn("issue.write", required)
        self.assertEqual(("issue.explode",), unknown)


class CapabilityPreflightTests(unittest.TestCase):
    """R13 - an incomplete route fails preflight without partial writes."""

    def test_a_complete_route_passes(self) -> None:
        report = require_capabilities(
            GitHubCliTransport("gh"), ["issue.create", "project.add_item"]
        )

        self.assertTrue(report.complete)

    def test_an_incomplete_route_is_refused_before_any_write(self) -> None:
        with self.assertRaises(CapabilityError) as raised:
            require_capabilities(_Incomplete(), ["issue.create", "project.add_item"])

        message = str(raised.exception)
        self.assertIn("generic-mcp", message)
        self.assertIn("project.item.write", message)

    def test_an_incomplete_route_still_passes_what_it_can_do(self) -> None:
        report = require_capabilities(_Incomplete(), ["issue.create"])

        self.assertTrue(report.complete)

    def test_the_report_names_every_missing_capability(self) -> None:
        report = inspect_route(
            _Incomplete(), ["project.view.create", "project.field.create"]
        )

        self.assertFalse(report.complete)
        self.assertEqual(
            {"project.view.write", "project.field.write"}, set(report.missing)
        )

    def test_an_unknown_action_kind_is_refused(self) -> None:
        with self.assertRaisesRegex(CapabilityError, "unknown action kinds"):
            require_capabilities(GitHubCliTransport("gh"), ["issue.teleport"])


class RouteParityTests(unittest.TestCase):
    """R13 - peer routes must behave identically, not merely both exist.

    The CLI route once could not fall back from an unavailable native issue
    type because `gh api` reports every failure as exit code 1, while the same
    request through the direct API recovered. These drive one service through
    both transports and assert the outcomes agree.
    """

    def _cli_service(self, responses: list[CompletedProcess]) -> tuple:
        sent: list[dict] = []
        service = GitHubService(
            GitHubCliTransport("gh"),
            owner="o",
            repository="r",
            project_number=1,
            issue_type_mode="native_or_label",
        )

        def run(command, **kwargs):
            sent.append(json.loads(kwargs["input"]) if kwargs.get("input") else {})
            return responses.pop(0)

        return service, sent, run

    def _api_service(self, responses: list) -> tuple:
        sent: list[dict] = []
        service = GitHubService(
            GitHubHttpTransport("token"),
            owner="o",
            repository="r",
            project_number=1,
            issue_type_mode="native_or_label",
        )

        def urlopen(request, timeout=None):
            sent.append(json.loads(request.data.decode()) if request.data else {})
            result = responses.pop(0)
            if isinstance(result, HTTPError):
                raise result
            return result

        return service, sent, urlopen

    @staticmethod
    def _ok(payload: dict) -> io.BytesIO:
        stream = io.BytesIO(json.dumps(payload).encode())
        stream.status = 200
        return stream

    @staticmethod
    def _issue_payload() -> dict:
        return {"number": 7, "id": 70, "node_id": "I_7", "html_url": "u"}

    def _payload(self) -> dict:
        return {
            "title": "T",
            "body": "b",
            "type": "Story",
            "fallback_label": "type:story",
        }

    def test_both_routes_create_an_issue_with_the_same_request(self) -> None:
        cli_service, cli_sent, run = self._cli_service(
            [CompletedProcess(["gh"], 0, stdout=json.dumps(self._issue_payload()))]
        )
        with patch("agentic_backlog_kit.github.subprocess.run", side_effect=run):
            cli_ref = cli_service.create_issue("T-1", self._payload())

        api_service, api_sent, urlopen = self._api_service(
            [self._ok(self._issue_payload())]
        )
        with patch("agentic_backlog_kit.github.urlopen", side_effect=urlopen):
            api_ref = api_service.create_issue("T-1", self._payload())

        self.assertEqual(cli_sent, api_sent)
        self.assertEqual(cli_ref.number, api_ref.number)

    def test_both_routes_fall_back_to_a_label_on_an_unavailable_type(self) -> None:
        """The exact regression: this diverged until the CLI 422 was recovered."""

        cli_service, cli_sent, run = self._cli_service(
            [
                CompletedProcess(
                    ["gh"], 1, stdout="", stderr="gh: Validation Failed (HTTP 422)"
                ),
                CompletedProcess(["gh"], 0, stdout=json.dumps(self._issue_payload())),
            ]
        )
        with patch("agentic_backlog_kit.github.subprocess.run", side_effect=run):
            cli_service.create_issue("T-1", self._payload())

        api_service, api_sent, urlopen = self._api_service(
            [
                HTTPError("u", 422, "Validation Failed", None, io.BytesIO(b"{}")),
                self._ok(self._issue_payload()),
            ]
        )
        with patch("agentic_backlog_kit.github.urlopen", side_effect=urlopen):
            api_service.create_issue("T-1", self._payload())

        self.assertEqual(cli_sent, api_sent)
        # Both attempted the native type, then both retried with the label.
        self.assertEqual("Story", cli_sent[0]["type"])
        self.assertNotIn("type", cli_sent[1])
        self.assertEqual(["type:story"], cli_sent[1]["labels"])

    def test_both_routes_stay_fatal_on_a_failure_neither_can_recover(self) -> None:
        cli_service, _, run = self._cli_service(
            [CompletedProcess(["gh"], 1, stdout="", stderr="gh: Server Error (HTTP 500)")]
        )
        with patch("agentic_backlog_kit.github.subprocess.run", side_effect=run):
            with self.assertRaises(Exception) as cli_error:
                cli_service.create_issue("T-1", self._payload())

        api_service, _, urlopen = self._api_service(
            [HTTPError("u", 500, "Server Error", None, io.BytesIO(b"{}"))]
        )
        with patch("agentic_backlog_kit.github.urlopen", side_effect=urlopen):
            with self.assertRaises(Exception) as api_error:
                api_service.create_issue("T-1", self._payload())

        self.assertEqual(
            getattr(cli_error.exception, "status", None),
            getattr(api_error.exception, "status", None),
        )


if __name__ == "__main__":
    unittest.main()
