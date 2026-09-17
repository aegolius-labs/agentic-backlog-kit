"""Keep the Codex and Claude Code plugin manifests from drifting apart.

`skills/` is the single source of truth for behavior. Each supported host gets a
thin manifest over it. These tests enforce that the manifests describe the same
plugin, that every host discovers the same skill set, and that the marketplace
entry agrees with the plugin manifest it points at.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODEX_MANIFEST = ROOT / ".codex-plugin" / "plugin.json"
CLAUDE_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
CLAUDE_MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_version(version: str) -> str:
    """Strip build metadata so each host can carry its own provenance suffix."""

    return version.split("+", 1)[0]


class HostManifestParityTests(unittest.TestCase):
    def test_every_supported_host_manifest_exists(self) -> None:
        for path in (CODEX_MANIFEST, CLAUDE_MANIFEST, CLAUDE_MARKETPLACE):
            self.assertTrue(path.is_file(), f"missing host manifest: {path}")

    def test_identity_agrees_across_hosts(self) -> None:
        codex = _load(CODEX_MANIFEST)
        claude = _load(CLAUDE_MANIFEST)

        self.assertEqual(codex["name"], claude["name"])
        self.assertEqual(codex["description"], claude["description"])
        self.assertEqual(
            _base_version(codex["version"]), _base_version(claude["version"])
        )

    def test_marketplace_entry_matches_plugin_manifest(self) -> None:
        claude = _load(CLAUDE_MANIFEST)
        marketplace = _load(CLAUDE_MARKETPLACE)

        entries = [
            entry
            for entry in marketplace["plugins"]
            if entry["name"] == claude["name"]
        ]
        self.assertEqual(1, len(entries), "expected exactly one marketplace entry")
        entry = entries[0]

        self.assertEqual(claude["description"], entry["description"])
        self.assertEqual(
            _base_version(claude["version"]), _base_version(entry["version"])
        )

        source = entry["source"]
        self.assertIsInstance(source, str, "local marketplace source must be a path")
        resolved = (ROOT / source).resolve()
        self.assertTrue(resolved.is_dir(), f"marketplace source does not resolve: {source}")
        self.assertTrue(
            (resolved / ".claude-plugin" / "plugin.json").is_file(),
            "marketplace source does not contain a Claude Code plugin manifest",
        )

    def test_both_hosts_discover_the_same_skills(self) -> None:
        on_disk = {
            path.name
            for path in (ROOT / "skills").iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }
        self.assertTrue(on_disk, "no skills found")

        # Codex declares an explicit skills directory; Claude Code auto-discovers
        # `skills/` unless the manifest overrides it. Neither host may narrow the
        # set without the other doing the same.
        self.assertEqual("./skills/", _load(CODEX_MANIFEST)["skills"])
        self.assertNotIn(
            "skills",
            _load(CLAUDE_MANIFEST),
            "Claude Code manifest must rely on default skills/ discovery",
        )

        for name in sorted(on_disk):
            body = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(
                body.startswith("---\n"), f"{name}: SKILL.md needs YAML frontmatter"
            )
            self.assertIn(f"name: {name}\n", body, f"{name}: frontmatter name mismatch")

    def test_claude_skill_frontmatter_is_within_host_limits(self) -> None:
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            frontmatter = path.read_text(encoding="utf-8").split("---", 2)[1]
            fields = {}
            for line in frontmatter.splitlines():
                if ":" in line and not line.startswith(" "):
                    key, _, value = line.partition(":")
                    fields[key.strip()] = value.strip()

            name = fields.get("name", "")
            description = fields.get("description", "")
            self.assertTrue(name, f"{path}: missing name")
            self.assertTrue(description, f"{path}: missing description")
            self.assertLessEqual(len(name), 64, f"{path}: name exceeds 64 characters")
            self.assertLessEqual(
                len(description), 1024, f"{path}: description exceeds 1024 characters"
            )
            self.assertRegex(
                name, r"^[a-z0-9]+(-[a-z0-9]+)*$", f"{path}: name must be kebab-case"
            )


if __name__ == "__main__":
    unittest.main()
