"""Stamp one computed release version across every declaration in the tree.

Version calculation is delegated to the organization's reusable workflow, which
derives the next semantic version from Conventional Commit history.  Nothing
propagated that answer back into the package, so a release-bearing merge
computed a tag the tree could not match and preflight refused it (R14-F8).
Bumping five declarations by hand before every merge is not delegation; it is
the same manual step with an extra chance to forget.

This script is that missing propagation.  Release preflight runs it against the
candidate checkout before building, so the distributions carry the computed
version and the release check compares like with like.  Nothing is committed or
pushed: the tag remains the record of what a version means.

It is also safe to run locally when a version genuinely needs to be pinned in
the tree, and running it twice with the same version changes nothing.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Iterable


SEMANTIC_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


class VersionStampError(RuntimeError):
    """Raised when a declaration cannot be stamped, before anything is written."""


@dataclass(frozen=True, slots=True)
class Declaration:
    path: str
    pattern: re.Pattern[str]
    template: str


DECLARATIONS: tuple[Declaration, ...] = (
    Declaration(
        "pyproject.toml",
        re.compile(r'(?m)^(version\s*=\s*")[^"]+(")$'),
        r"\g<1>{version}\g<2>",
    ),
    Declaration(
        ".codex-plugin/plugin.json",
        re.compile(r'("version"\s*:\s*")[^"]+(")'),
        r"\g<1>{version}\g<2>",
    ),
    Declaration(
        ".claude-plugin/plugin.json",
        re.compile(r'("version"\s*:\s*")[^"]+(")'),
        r"\g<1>{version}\g<2>",
    ),
    Declaration(
        ".claude-plugin/marketplace.json",
        re.compile(r'("version"\s*:\s*")[^"]+(")'),
        r"\g<1>{version}\g<2>",
    ),
    Declaration(
        "src/agentic_backlog_kit/__init__.py",
        re.compile(r'(?m)^(__version__\s*=\s*")[^"]+(")$'),
        r"\g<1>{version}\g<2>",
    ),
)

UNRELEASED_HEADING = "## [Unreleased]"
NO_ENTRIES_NOTE = "_No curated entries were recorded; see the release notes._"


def _read(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise VersionStampError(f"missing {relative}")
    return path.read_text(encoding="utf-8")


def stamp_declarations(root: Path, version: str) -> list[str]:
    """Write the version into every declaration, or raise before writing any."""

    planned: list[tuple[Path, str]] = []
    for declaration in DECLARATIONS:
        original = _read(root, declaration.path)
        updated, count = declaration.pattern.subn(
            declaration.template.format(version=version), original, count=1
        )
        if count != 1:
            raise VersionStampError(
                f"{declaration.path} has no version declaration to stamp"
            )
        planned.append((root / declaration.path, updated))

    changed: list[str] = []
    for path, content in planned:
        if path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
            changed.append(path.name)
    return changed


def promote_changelog(root: Path, version: str, released_on: str) -> bool:
    """Turn the Unreleased section into this version's entry.

    Contributors write under ``## [Unreleased]`` without knowing which version
    their change will land in.  The release knows, so it stamps the heading and
    opens a fresh Unreleased section behind it.
    """

    content = _read(root, "CHANGELOG.md")
    if re.search(rf"(?m)^## \[{re.escape(version)}\](?:\s|$)", content):
        return False
    if UNRELEASED_HEADING not in content:
        raise VersionStampError(
            f"CHANGELOG.md has neither a [{version}] entry nor an Unreleased section"
        )

    head, _, tail = content.partition(UNRELEASED_HEADING)
    next_heading = re.search(r"(?m)^## \[", tail)
    if next_heading:
        body, remainder = tail[: next_heading.start()], tail[next_heading.start() :]
    else:
        body, remainder = tail, ""

    entries = body.strip("\n").strip()
    if not entries:
        entries = NO_ENTRIES_NOTE

    rebuilt = (
        f"{head}{UNRELEASED_HEADING}\n\n"
        f"## [{version}] - {released_on}\n\n"
        f"{entries}\n\n"
        f"{remainder}"
    )
    (root / "CHANGELOG.md").write_text(rebuilt, encoding="utf-8")
    return True


def set_version(root: Path, version: str, released_on: str) -> dict[str, object]:
    if not SEMANTIC_VERSION.match(version):
        raise VersionStampError(f"{version!r} is not a semantic version")
    changed = stamp_declarations(root, version)
    promoted = promote_changelog(root, version, released_on)
    return {"version": version, "changed": changed, "changelog_promoted": promoted}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stamp the computed release version across the tree"
    )
    parser.add_argument("--version", required=True, help="for example 0.2.0")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--date", help="release date, defaults to today (UTC)")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    version = args.version.lstrip("v")
    released_on = args.date or date_type.today().isoformat()
    try:
        result = set_version(Path(args.root).resolve(), version, released_on)
    except VersionStampError as error:
        print(f"version stamp failed: {error}", file=sys.stderr)
        return 1
    changed = ", ".join(result["changed"]) or "nothing"
    print(
        f"stamped version={result['version']} changed={changed} "
        f"changelog_promoted={result['changelog_promoted']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
