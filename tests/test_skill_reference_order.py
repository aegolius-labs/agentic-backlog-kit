"""Skills whose references carry their rules read them as the first step.

The Claude Code evaluation (S-R31-2, docs/validation.md F1 and F2) found the
sync skill stopping before its mapping reference when GitHub was unreachable,
and indirect sprint planning skipping its contract. Putting the read in step 1
removes the paths that skipped it.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILLS = Path(__file__).resolve().parents[1] / "skills"


def _first_step(skill: str) -> str:
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"^1\. (.+)$", text, re.MULTILINE)
    assert match, f"{skill} has no numbered first step"
    return match.group(1)


class SkillReferenceOrderTests(unittest.TestCase):
    def test_first_step_reads_the_rules_reference(self) -> None:
        for skill, reference in (
            ("backlog-sync-github", "references/github-mapping.md"),
            ("backlog-sprint-plan", "references/sprint-contract.md"),
        ):
            with self.subTest(skill=skill):
                step = _first_step(skill)
                self.assertTrue(step.startswith("Read ["), step)
                self.assertIn(reference, step)


if __name__ == "__main__":
    unittest.main()
