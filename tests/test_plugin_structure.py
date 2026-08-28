from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SKILLS = {
    "backlog-init",
    "backlog-ingest",
    "backlog-prioritize",
    "backlog-sprint-plan",
    "backlog-sync-github",
}


class PluginStructureTests(unittest.TestCase):
    def test_manifest_and_declared_skill_directory_exist(self) -> None:
        plugin = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )

        self.assertEqual("agentic-backlog-kit", plugin["name"])
        self.assertEqual("./skills/", plugin["skills"])
        self.assertEqual("0.1.0", plugin["version"])

    def test_all_focused_skills_have_metadata_and_no_placeholders(self) -> None:
        actual = {
            path.name for path in (ROOT / "skills").iterdir() if path.is_dir()
        }
        self.assertEqual(EXPECTED_SKILLS, actual)

        for skill_name in sorted(EXPECTED_SKILLS):
            skill_dir = ROOT / "skills" / skill_name
            instructions = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            metadata = (skill_dir / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
            self.assertTrue(instructions.startswith("---\nname:"))
            self.assertIn(f"name: {skill_name}\n", instructions)
            self.assertIn("description:", instructions)
            self.assertNotIn("TODO", instructions)
            self.assertIn("default_prompt:", metadata)


if __name__ == "__main__":
    unittest.main()
