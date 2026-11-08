"""R37: opt-in usage evidence under the organization's usage evidence contract.

`tests/fixtures/usage/` is the contract's shared fixture. Other kits carry a
byte-identical copy; keep them together and say so when it changes.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agentic_backlog_kit import usage
from agentic_backlog_kit.cli import main
from agentic_backlog_kit.usage import UsageError

from tests import helpers


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "usage"
CLEAN_ENV = {
    key: value
    for key, value in os.environ.items()
    if key not in {"CLAUDECODE", usage.HOST_ENV, usage.INITIATOR_ENV, usage.RUN_ID_ENV}
}


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class _Project(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._cwd = os.getcwd()
        os.chdir(self.root)
        self._env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self._env.start()
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps(helpers.manifest()), encoding="utf-8")

    def tearDown(self) -> None:
        self._env.stop()
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def run_cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            status = main(list(argv))
        return status, out.getvalue()

    @property
    def events(self) -> list[dict]:
        return _lines(self.root / usage.USAGE_DIR / usage.EVENTS_FILE)


class FixtureTests(unittest.TestCase):
    def test_the_shared_fixture_is_accepted(self) -> None:
        usage.validate_config(json.loads((FIXTURE / "config.json").read_text(encoding="utf-8")))
        for event in _lines(FIXTURE / "events.jsonl"):
            usage.validate_event(event)
        for note in _lines(FIXTURE / "feedback.jsonl"):
            usage.validate_feedback(note)

    def test_forbidden_fields_are_rejected(self) -> None:
        event = _lines(FIXTURE / "events.jsonl")[0]
        for field, value in (
            ("path", "src/app.py"),
            ("repository", "owner/repo"),
            ("arguments", ["--manifest", "x.json"]),
            ("message", "boom"),
            ("user", "someone"),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(UsageError, "forbids"):
                usage.validate_event({**event, field: value})
        with self.assertRaisesRegex(UsageError, "bare command name"):
            usage.validate_event({**event, "command": "sync-apply --confirm abc"})
        with self.assertRaisesRegex(UsageError, "fixed code"):
            usage.validate_event({**event, "error_class": "could not open C:/x"})

    def test_friction_that_looks_like_project_data_is_rejected(self) -> None:
        for phrase in (
            "failed on C:\\work\\repo",
            "see /home/me/project",
            "broke in src/app.py",
            "check https://example.com/issue",
            "mail me at a@b.co",
            "token ghp_abcdefghijklmnop",
            "hash 0123456789abcdef0123456789abcdef",
        ):
            with self.subTest(phrase=phrase), self.assertRaisesRegex(UsageError, "path, URL"):
                usage.validate_friction([phrase])
        with self.assertRaisesRegex(UsageError, "at most 5"):
            usage.validate_friction(["slow"] * 6)
        usage.validate_friction(["the plan digest had to be copied by hand"])


class OptInTests(_Project):
    def test_a_project_without_the_opt_in_gets_no_usage_files(self) -> None:
        status, _ = self.run_cli("validate", "--manifest", str(self.manifest))

        self.assertEqual(0, status)
        self.assertFalse((self.root / usage.USAGE_DIR).exists())
        self.assertFalse((self.root / ".gitignore").exists())

    def test_enable_creates_config_and_gitignore_once(self) -> None:
        status, output = self.run_cli("usage", "enable")
        again, _ = self.run_cli("usage", "enable")

        self.assertEqual((0, 0), (status, again))
        config = usage.load_config(self.root)
        self.assertTrue(config["enabled"])
        self.assertIsNone(config["publish"])
        self.assertEqual(json.loads(output)["project_id"], config["project_id"])
        self.assertEqual(
            [".aegolius-usage/"],
            (self.root / ".gitignore").read_text(encoding="utf-8").splitlines(),
        )

    def test_each_command_records_one_event_with_nothing_from_the_project(self) -> None:
        self.run_cli("usage", "enable")
        self.run_cli("validate", "--manifest", str(self.manifest))
        self.run_cli("validate", "--manifest", str(self.root / "missing.json"))

        events = self.events
        self.assertEqual(["validate", "validate"], [e["command"] for e in events])
        self.assertEqual("ok", events[0]["outcome"])
        self.assertIsNone(events[0]["error_class"])
        self.assertNotEqual("ok", events[1]["outcome"])
        for event in events:
            usage.validate_event(event)
            self.assertEqual("unknown", event["host"])
            self.assertEqual("unknown", event["initiated_by"])
            self.assertNotIn(self._tmp.name, json.dumps(event))
            self.assertNotIn("manifest", json.dumps(event))

    def test_host_initiator_and_run_come_only_from_explicit_signals(self) -> None:
        self.run_cli("usage", "enable")
        with mock.patch.dict(
            os.environ,
            {
                "CLAUDECODE": "1",
                usage.INITIATOR_ENV: "agent",
                usage.RUN_ID_ENV: "r-0123456789ab",
            },
        ):
            self.run_cli("validate", "--manifest", str(self.manifest))
        with mock.patch.dict(os.environ, {usage.INITIATOR_ENV: "robot"}):
            self.run_cli("validate", "--manifest", str(self.manifest))

        first, second = self.events
        self.assertEqual(
            ("claude-code", "agent", "r-0123456789ab"),
            (first["host"], first["initiated_by"], first["run_id"]),
        )
        self.assertEqual(("unknown", "unknown"), (second["host"], second["initiated_by"]))

    def test_usage_commands_are_not_recorded_and_disable_stops_recording(self) -> None:
        self.run_cli("usage", "enable")
        self.run_cli("usage", "report")
        self.run_cli("usage", "disable")
        self.run_cli("validate", "--manifest", str(self.manifest))

        self.assertEqual([], self.events)
        self.assertFalse(usage.load_config(self.root)["enabled"])

    def test_purge_deletes_the_folder(self) -> None:
        self.run_cli("usage", "enable")
        self.run_cli("validate", "--manifest", str(self.manifest))

        status, _ = self.run_cli("usage", "purge")

        self.assertEqual(0, status)
        self.assertFalse((self.root / usage.USAGE_DIR).exists())


class FeedbackAndReportTests(_Project):
    def test_feedback_needs_the_opt_in_and_is_validated(self) -> None:
        status, _ = self.run_cli("usage", "feedback", "--verdict", "helped", "--source", "person")
        self.assertEqual(1, status)

        self.run_cli("usage", "enable")
        status, _ = self.run_cli(
            "usage", "feedback", "--verdict", "helped", "--source", "agent-judgment",
            "--friction", "see src/app.py",
        )
        self.assertEqual(1, status)
        status, _ = self.run_cli(
            "usage", "feedback", "--verdict", "helped", "--source", "agent-judgment",
            "--friction", "the plan digest had to be copied by hand",
        )
        self.assertEqual(0, status)
        notes = _lines(self.root / usage.USAGE_DIR / usage.FEEDBACK_FILE)
        self.assertEqual(1, len(notes))
        self.assertEqual("agent-judgment", notes[0]["source"])

    def test_report_withholds_small_counts_and_labels_agent_judgment(self) -> None:
        self.run_cli("usage", "enable")
        for _ in range(5):
            self.run_cli("validate", "--manifest", str(self.manifest))
        self.run_cli("summary", "--manifest", str(self.manifest))
        self.run_cli("usage", "feedback", "--verdict", "helped", "--source", "agent-judgment")

        report = usage.build_report([self.root])
        self.assertEqual(6, report["events"])
        self.assertEqual(5, report["by_command"]["agentic-backlog-kit validate"])
        self.assertEqual("<5", report["by_command"]["agentic-backlog-kit summary"])
        self.assertEqual({"numerator": 6, "denominator": 6, "withheld": False}, report["ok_rate"])
        self.assertEqual({"helped": "<5"}, report["feedback"]["agent-judgment"])

        status, markdown = self.run_cli("usage", "report", "--share")
        self.assertEqual(0, status)
        self.assertIn("6 of 6", markdown)
        self.assertIn("a model's opinion, not user evidence", markdown)
        self.assertNotIn(self._tmp.name, markdown)

    def test_report_over_nothing_withholds_the_rate(self) -> None:
        report = usage.build_report([self.root])

        self.assertEqual(0, report["projects"])
        self.assertTrue(report["ok_rate"]["withheld"])


class _FakeTransport:
    def __init__(self, issues: list[dict] | None = None) -> None:
        self.issues = issues or []
        self.calls: list[tuple[str, str, dict | None]] = []

    def rest(self, method: str, path: str, payload: dict | None = None):
        self.calls.append((method, path, payload))
        if method == "GET":
            return self.issues
        if path.endswith("/issues"):
            issue = {"number": 7, "title": payload["title"]}
            self.issues.append(issue)
            return issue
        return {"html_url": "https://github.com/example-owner/kit-usage/issues/7#c1"}


class PublishTests(_Project):
    def test_publish_refuses_without_the_owners_recorded_authorization(self) -> None:
        self.run_cli("usage", "enable")

        with self.assertRaisesRegex(UsageError, "owner's recorded authorization"):
            usage.publish(self.root, _FakeTransport())

    def test_publish_posts_one_comment_on_the_projects_issue(self) -> None:
        self.run_cli("usage", "enable")
        config = usage.load_config(self.root)
        config["publish"] = {
            "repository": "example-owner/kit-usage",
            "authorized_by": "the owner",
            "authorized_at": "2026-11-08T14:00:00Z",
        }
        usage._write_config(self.root, config)
        transport = _FakeTransport()

        first = usage.publish(self.root, transport)
        second = usage.publish(self.root, transport)

        self.assertTrue(first["issue_created"])
        self.assertFalse(second["issue_created"])
        posts = [call for call in transport.calls if call[0] == "POST"]
        self.assertEqual(
            [
                "/repos/example-owner/kit-usage/issues",
                "/repos/example-owner/kit-usage/issues/7/comments",
                "/repos/example-owner/kit-usage/issues/7/comments",
            ],
            [path for _, path, _ in posts],
        )
        self.assertEqual(config["project_id"], posts[0][2]["title"])
        self.assertIn("## Kit usage summary", posts[1][2]["body"])


if __name__ == "__main__":
    unittest.main()
