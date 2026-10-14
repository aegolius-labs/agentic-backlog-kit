"""S-R10-1: the skills that hand work to an agent require closing keywords.

Closure is automated from evidence: GitHub closes an issue when a pull request
carrying `Closes #N` merges. That only holds if agents are told to write the
keyword, and told not to close a parent with it prematurely.
"""

from __future__ import annotations

import unittest
from pathlib import Path


SKILLS = Path(__file__).resolve().parents[1] / "skills"


def _skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


class ClosingKeywordGuidanceTests(unittest.TestCase):
    def test_handoff_skills_require_a_closing_keyword(self) -> None:
        for name in ("backlog-prioritize", "backlog-sprint-plan"):
            with self.subTest(skill=name):
                self.assertIn("`Closes #N`", _skill(name))

    def test_parents_are_not_closed_by_a_child_pull_request(self) -> None:
        text = _skill("backlog-prioritize")
        self.assertIn("Do not close a parent", text)
        self.assertIn("acceptance criteria", text)


if __name__ == "__main__":
    unittest.main()
