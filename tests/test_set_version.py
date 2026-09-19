from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.release_check import validate_release
from scripts.set_version import (
    DECLARATIONS,
    NO_ENTRIES_NOTE,
    VersionStampError,
    set_version,
)

from tests.test_release_check import ROOT, VERSION, _write_artifacts


CHANGELOG = """# Changelog

The format follows Keep a Changelog.

## [Unreleased]

### Fixed

- Something worth releasing.

## [0.1.0] - 2026-09-04

### Added

- The first release.
"""


def _tree(directory: Path, *, changelog: str = CHANGELOG, version: str = "0.1.0") -> Path:
    """Build the minimum tree the stamper and the release check both read."""

    (directory / ".codex-plugin").mkdir()
    (directory / ".claude-plugin").mkdir()
    (directory / "src" / "agentic_backlog_kit").mkdir(parents=True)

    (directory / "pyproject.toml").write_text(
        f'[project]\nname = "agentic-backlog-kit"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    for manifest in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
        (directory / manifest).write_text(
            json.dumps({"name": "agentic-backlog-kit", "version": version}, indent=2),
            encoding="utf-8",
        )
    (directory / ".claude-plugin/marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "abk", "version": version}]}, indent=2),
        encoding="utf-8",
    )
    (directory / "src" / "agentic_backlog_kit" / "__init__.py").write_text(
        f'"""Kit."""\n\n__version__ = "{version}"\n', encoding="utf-8"
    )
    (directory / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return directory


class StampDeclarationsTests(unittest.TestCase):
    """R14-F8 - the computed version must reach every declaration."""

    def test_stamps_every_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = _tree(Path(directory))

            set_version(root, "0.2.0", "2026-09-19")

            for declaration in DECLARATIONS:
                text = (root / declaration.path).read_text(encoding="utf-8")
                self.assertIn("0.2.0", text, declaration.path)
                self.assertNotIn('"0.1.0"', text, declaration.path)

    def test_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = _tree(Path(directory))

            set_version(root, "0.2.0", "2026-09-19")
            second = set_version(root, "0.2.0", "2026-09-19")

            self.assertEqual([], second["changed"])
            self.assertFalse(second["changelog_promoted"])

    def test_rejects_a_non_semantic_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = _tree(Path(directory))

            with self.assertRaisesRegex(VersionStampError, "semantic version"):
                set_version(root, "latest", "2026-09-19")

    def test_writes_nothing_when_a_declaration_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = _tree(Path(directory))
            (root / ".codex-plugin" / "plugin.json").unlink()

            with self.assertRaises(VersionStampError):
                set_version(root, "0.2.0", "2026-09-19")

            # The failure must happen before any file is rewritten.
            self.assertIn(
                '"0.1.0"',
                (root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"),
            )

    def test_writes_nothing_when_a_declaration_has_no_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = _tree(Path(directory))
            (root / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")

            with self.assertRaisesRegex(VersionStampError, "no version declaration"):
                set_version(root, "0.2.0", "2026-09-19")

            self.assertIn(
                '__version__ = "0.1.0"',
                (root / "src" / "agentic_backlog_kit" / "__init__.py").read_text(
                    encoding="utf-8"
                ),
            )


class PromoteChangelogTests(unittest.TestCase):
    def test_promotes_the_unreleased_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = _tree(Path(directory))

            set_version(root, "0.2.0", "2026-09-19")

            changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
            self.assertIn("## [0.2.0] - 2026-09-19", changelog)
            self.assertIn("Something worth releasing.", changelog)
            self.assertIn("## [0.1.0] - 2026-09-04", changelog)
            # A fresh Unreleased section stays open for the next change.
            self.assertLess(
                changelog.index("## [Unreleased]"), changelog.index("## [0.2.0]")
            )

    def test_keeps_an_existing_entry_for_the_same_version(self) -> None:
        existing = CHANGELOG.replace("## [Unreleased]", "## [0.2.0] - 2026-09-01")
        with tempfile.TemporaryDirectory() as directory:
            root = _tree(Path(directory), changelog=existing)

            result = set_version(root, "0.2.0", "2026-09-19")

            self.assertFalse(result["changelog_promoted"])
            self.assertIn(
                "## [0.2.0] - 2026-09-01",
                (root / "CHANGELOG.md").read_text(encoding="utf-8"),
            )

    def test_notes_an_empty_unreleased_section_rather_than_blocking(self) -> None:
        empty = "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-09-04\n\n- First.\n"
        with tempfile.TemporaryDirectory() as directory:
            root = _tree(Path(directory), changelog=empty)

            set_version(root, "0.2.0", "2026-09-19")

            changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
            self.assertIn("## [0.2.0] - 2026-09-19", changelog)
            self.assertIn(NO_ENTRIES_NOTE, changelog)

    def test_rejects_a_changelog_with_no_unreleased_section(self) -> None:
        without = "# Changelog\n\n## [0.1.0] - 2026-09-04\n\n- First.\n"
        with tempfile.TemporaryDirectory() as directory:
            root = _tree(Path(directory), changelog=without)

            with self.assertRaisesRegex(VersionStampError, "Unreleased"):
                set_version(root, "0.2.0", "2026-09-19")


class StampSatisfiesReleaseCheckTests(unittest.TestCase):
    """The whole point: a stamped tree passes the check that refused the merge."""

    def test_a_stamped_tree_validates_against_the_computed_tag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            # Copy the real tree so the check sees genuine metadata, then stamp.
            for name in (
                "pyproject.toml",
                "CHANGELOG.md",
                ".codex-plugin",
                ".claude-plugin",
            ):
                source = ROOT / name
                target = root / name
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copy2(source, target)
            package = root / "src" / "agentic_backlog_kit"
            package.mkdir(parents=True)
            shutil.copy2(ROOT / "src" / "agentic_backlog_kit" / "__init__.py", package)

            # Move the tree off the real version, then stamp it back, so the
            # check is validating what the stamper wrote rather than what was
            # already there.
            set_version(root, "0.0.1", "2026-09-19")
            self.assertIn(
                'version = "0.0.1"',
                (root / "pyproject.toml").read_text(encoding="utf-8"),
            )

            set_version(root, VERSION, "2026-09-19")

            dist = root / "dist"
            dist.mkdir()
            _write_artifacts(dist)

            report = validate_release(root, dist, tag=f"v{VERSION}")

            self.assertEqual(VERSION, report.version)


if __name__ == "__main__":
    unittest.main()
