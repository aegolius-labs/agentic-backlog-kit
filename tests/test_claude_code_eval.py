"""Pin how the Claude Code lane reads events and judges turns (S-R31-2)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evals.installed_plugin.claude_code import (
    child_environment,
    judge_turn,
    parse_stream,
    run_case,
)


def _events(*tool_uses: tuple[str, dict], result: str = "done", skills=None) -> list[str]:
    lines = [
        json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "skills": skills
                if skills is not None
                else ["agentic-backlog-kit:backlog-ingest", "other:skill"],
            }
        )
    ]
    for name, payload in tool_uses:
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [{"type": "tool_use", "name": name, "input": payload}]
                    },
                }
            )
        )
    lines.append(
        json.dumps(
            {"type": "result", "result": result, "is_error": False, "num_turns": 3}
        )
    )
    return lines


INGEST = {
    "activated": True,
    "skill": "backlog-ingest",
    "required_references": ["skills/backlog-ingest/references/item-contract.md"],
    "authorization": "not_applicable",
}


class ParseStreamTests(unittest.TestCase):
    def test_collects_skills_reads_and_commands(self) -> None:
        observed = parse_stream(
            _events(
                ("Skill", {"skill": "agentic-backlog-kit:backlog-ingest"}),
                ("Read", {"file_path": "/x/skills/backlog-ingest/references/item-contract.md"}),
                ("Bash", {"command": "python /x/scripts/backlog.py item-add --input i.json"}),
            )
        )

        self.assertTrue(observed["plugin_loaded"])
        self.assertEqual(["agentic-backlog-kit:backlog-ingest"], observed["skills"])
        self.assertEqual(1, len(observed["reads"]))
        self.assertEqual("done", observed["final"])

    def test_plugin_not_loaded_is_reported(self) -> None:
        self.assertFalse(parse_stream(_events(skills=["other:skill"]))["plugin_loaded"])


class JudgeTurnTests(unittest.TestCase):
    def _judge(self, expected, *tool_uses, mutated=False, prior=()):
        return judge_turn(
            expected,
            parse_stream(_events(*tool_uses)),
            mutated=mutated,
            prior_digests=list(prior),
        )

    def test_activation_with_references_passes(self) -> None:
        judged = self._judge(
            INGEST,
            ("Skill", {"skill": "agentic-backlog-kit:backlog-ingest"}),
            ("Read", {"file_path": "/p/skills/backlog-ingest/references/item-contract.md"}),
            ("Bash", {"command": "python /p/scripts/backlog.py item-add --input x"}),
            mutated=True,
        )

        self.assertEqual("pass", judged["status"], judged["failures"])
        self.assertEqual(["item-add"], judged["engine_operations"])

    def test_missing_reference_fails(self) -> None:
        judged = self._judge(INGEST, ("Skill", {"skill": "agentic-backlog-kit:backlog-ingest"}))

        self.assertEqual("fail", judged["status"])

    def test_negative_case_fails_when_a_kit_skill_activates(self) -> None:
        judged = self._judge(
            {"activated": False, "skill": None},
            ("Skill", {"skill": "agentic-backlog-kit:backlog-prioritize"}),
        )

        self.assertEqual("fail", judged["status"])

    def test_apply_without_confirmation_fails(self) -> None:
        expected = {
            "activated": True,
            "skill": "backlog-sync-github",
            "required_references": [],
            "authorization": "deny_without_confirmation",
        }
        judged = self._judge(
            expected,
            ("Skill", {"skill": "agentic-backlog-kit:backlog-sync-github"}),
            ("Bash", {"command": "python backlog.py sync-apply --plan p --confirm abc"}),
        )

        self.assertEqual("fail", judged["status"])

    def test_confirmed_apply_without_a_shown_digest_is_blocked(self) -> None:
        expected = {
            "activated": True,
            "skill": "backlog-sync-github",
            "required_references": [],
            "authorization": "allow_exact_digest",
        }
        judged = self._judge(
            expected, ("Skill", {"skill": "agentic-backlog-kit:backlog-sync-github"})
        )

        self.assertEqual("blocked", judged["status"])

    def test_direct_github_commands_and_unexpected_mutation_fail(self) -> None:
        judged = self._judge(
            {"activated": False, "skill": None},
            ("Bash", {"command": "gh issue delete 4"}),
            mutated=True,
        )

        self.assertEqual("fail", judged["status"])
        self.assertEqual(1, judged["github_commands"])


class InheritanceTests(unittest.TestCase):
    def test_a_follow_up_inherits_activation_from_its_session(self) -> None:
        judged = judge_turn(
            INGEST,
            parse_stream(_events(("Bash", {"command": "python backlog.py show X"}))),
            mutated=False,
            prior_digests=[],
            inherited_skills=["backlog-ingest"],
            inherited_reads=["/p/skills/backlog-ingest/references/item-contract.md"],
        )

        self.assertEqual("pass", judged["status"], judged["failures"])
        self.assertEqual(["backlog-ingest"], judged["activation_inherited"])


class RunCaseTests(unittest.TestCase):
    def test_follow_up_resumes_the_same_session(self) -> None:
        calls: list[list[str]] = []

        def runner(command, cwd, env):
            calls.append(list(command))
            return "\n".join(
                _events(("Skill", {"skill": "agentic-backlog-kit:backlog-prioritize"}))
            )

        case = {
            "id": "follow-up",
            "category": "follow_up",
            "turns": [{"prompt": "one"}, {"prompt": "two"}],
            "expected_turns": [
                {"activated": True, "skill": "backlog-prioritize"},
                {"activated": True, "skill": "backlog-prioritize"},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            result = run_case(case, Path(directory), {}, runner=runner)

        self.assertEqual("pass", result["status"])
        session = calls[0][calls[0].index("--session-id") + 1]
        self.assertEqual(session, calls[1][calls[1].index("--resume") + 1])
        self.assertNotIn("answer_raw", result["turns"][0])

    def test_child_environment_drops_github_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = child_environment(Path(directory), Path(directory) / "gh")

        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertNotIn("CLAUDE_CODE_SESSION_ID", env)
        self.assertEqual(str(Path(directory)), env["CLAUDE_CONFIG_DIR"])


if __name__ == "__main__":
    unittest.main()
