"""Validate package metadata and release artifacts before publication.

The release workflow is intentionally tag-driven, so a bad tag must fail before
GitHub creates a release.  This module keeps the check dependency-free and
also verifies the files that ``python -m build`` places in ``dist``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
import tomllib
import zipfile
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path
from typing import Iterable


class ReleaseCheckError(ValueError):
    """Raised when release metadata or artifacts are unsafe to publish."""


@dataclass(frozen=True)
class ArtifactReport:
    """A validated release artifact and its reproducible local observations."""

    kind: str
    name: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ReleaseReport:
    """The result of a successful release preflight."""

    version: str
    artifacts: tuple[ArtifactReport, ...]


_INIT_VERSION = re.compile(
    r"^__version__\s*=\s*([\"'])(?P<version>[^\"']+)\1\s*$", re.MULTILINE
)
def _require_file(path: Path, description: str) -> Path:
    if not path.is_file():
        raise ReleaseCheckError(f"missing {description}: {path}")
    return path


def _metadata_version(root: Path) -> str:
    pyproject_path = _require_file(root / "pyproject.toml", "pyproject.toml")
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ReleaseCheckError(f"cannot read pyproject.toml: {exc}") from exc

    project = pyproject.get("project")
    project_name = project.get("name") if isinstance(project, dict) else None
    version = project.get("version") if isinstance(project, dict) else None
    if project_name != "agentic-backlog-kit":
        raise ReleaseCheckError(
            f"project.name must be 'agentic-backlog-kit'; got {project_name!r}"
        )
    if not isinstance(version, str) or not version:
        raise ReleaseCheckError("project.version must be a non-empty string")

    plugin_path = _require_file(root / ".codex-plugin" / "plugin.json", "plugin manifest")
    try:
        plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseCheckError(f"cannot read plugin manifest: {exc}") from exc
    plugin_name = plugin.get("name") if isinstance(plugin, dict) else None
    plugin_version = plugin.get("version") if isinstance(plugin, dict) else None
    if plugin_name != "agentic-backlog-kit":
        raise ReleaseCheckError(
            f"plugin name must be 'agentic-backlog-kit'; got {plugin_name!r}"
        )

    init_path = _require_file(
        root / "src" / "agentic_backlog_kit" / "__init__.py", "runtime version file"
    )
    match = _INIT_VERSION.search(init_path.read_text(encoding="utf-8"))
    runtime_version = match.group("version") if match else None

    observed = {
        "pyproject.toml": version,
        ".codex-plugin/plugin.json": plugin_version,
        "src/agentic_backlog_kit/__init__.py": runtime_version,
    }
    mismatches = {
        name: value for name, value in observed.items() if value != version
    }
    if mismatches:
        details = ", ".join(f"{name}={value!r}" for name, value in observed.items())
        raise ReleaseCheckError(f"version mismatch ({details})")

    changelog = _require_file(root / "CHANGELOG.md", "changelog")
    heading = re.compile(rf"^## \[{re.escape(version)}\](?:\s|$)", re.MULTILINE)
    if not heading.search(changelog.read_text(encoding="utf-8")):
        raise ReleaseCheckError(f"CHANGELOG.md has no [{version}] release entry")

    return version


def _validate_tag(version: str, tag: str | None) -> None:
    if tag is not None and tag != f"v{version}":
        raise ReleaseCheckError(
            f"tag {tag!r} does not match package version {version!r}; expected 'v{version}'"
        )


def _read_wheel_metadata(path: Path, version: str) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_names = [
                name
                for name in archive.namelist()
                if re.fullmatch(r"agentic_backlog_kit-[^/]+\.dist-info/METADATA", name)
            ]
            if len(metadata_names) != 1:
                raise ReleaseCheckError(
                    f"wheel {path.name} must contain exactly one dist-info/METADATA"
                )
            metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
            if metadata.get("Name") != "agentic-backlog-kit":
                raise ReleaseCheckError(
                    f"wheel {path.name} has unexpected Name: {metadata.get('Name')!r}"
                )
            if metadata.get("Version") != version:
                raise ReleaseCheckError(
                    f"wheel {path.name} metadata version {metadata.get('Version')!r} "
                    f"does not match {version!r}"
                )
            entry_points_names = [
                name
                for name in archive.namelist()
                if re.fullmatch(r"agentic_backlog_kit-[^/]+\.dist-info/entry_points\.txt", name)
            ]
            if len(entry_points_names) != 1:
                raise ReleaseCheckError(
                    f"wheel {path.name} must contain exactly one entry_points.txt"
                )
            entry_points = archive.read(entry_points_names[0]).decode("utf-8")
            if "abk = agentic_backlog_kit.cli:main" not in entry_points:
                raise ReleaseCheckError(
                    f"wheel {path.name} is missing the abk console entry point"
                )
    except zipfile.BadZipFile as exc:
        raise ReleaseCheckError(f"wheel {path.name} is not a valid ZIP archive") from exc


def _validate_sdist(path: Path, version: str) -> None:
    expected_root = f"agentic_backlog_kit-{version}"
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            names = [member.name.replace("\\", "/") for member in members]
    except (tarfile.TarError, OSError) as exc:
        raise ReleaseCheckError(f"sdist {path.name} is not a valid gzip tar archive") from exc

    top_levels = {name.split("/", 1)[0] for name in names if name}
    if top_levels != {expected_root}:
        raise ReleaseCheckError(
            f"sdist {path.name} must contain only top-level directory {expected_root!r}; "
            f"found {sorted(top_levels)!r}"
        )

    required = {
        f"{expected_root}/pyproject.toml",
        f"{expected_root}/README.md",
        f"{expected_root}/LICENSE.md",
        f"{expected_root}/src/agentic_backlog_kit/__init__.py",
    }
    missing = sorted(required.difference(names))
    if missing:
        raise ReleaseCheckError(
            f"sdist {path.name} is missing required source files: {', '.join(missing)}"
        )


def _artifact_report(path: Path, kind: str) -> ArtifactReport:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ArtifactReport(kind, path.name, path.stat().st_size, digest)


def _validate_artifacts(dist: Path, version: str) -> tuple[ArtifactReport, ...]:
    if not dist.is_dir():
        raise ReleaseCheckError(f"missing distribution directory: {dist}")
    files = sorted(path for path in dist.iterdir() if path.is_file())
    expected_sdist = f"agentic_backlog_kit-{version}.tar.gz"
    wheels = [
        path
        for path in files
        if path.name.startswith(f"agentic_backlog_kit-{version}-")
        and path.name.endswith(".whl")
    ]
    sdists = [path for path in files if path.name == expected_sdist]
    if len(wheels) != 1:
        raise ReleaseCheckError(
            f"expected exactly one wheel for version {version}; found {[p.name for p in wheels]!r}"
        )
    if len(sdists) != 1:
        raise ReleaseCheckError(
            f"expected exactly one sdist named {expected_sdist}; found {[p.name for p in sdists]!r}"
        )
    expected_names = {wheels[0].name, expected_sdist}
    unexpected = sorted(path.name for path in files if path.name not in expected_names)
    if unexpected:
        raise ReleaseCheckError(
            "distribution directory contains unexpected release assets: "
            + ", ".join(unexpected)
        )

    _read_wheel_metadata(wheels[0], version)
    _validate_sdist(sdists[0], version)
    return (
        _artifact_report(wheels[0], "wheel"),
        _artifact_report(sdists[0], "sdist"),
    )


def validate_release(
    root: Path, dist: Path | None = None, *, tag: str | None = None
) -> ReleaseReport:
    """Validate release metadata and exactly one wheel plus one sdist."""

    root = root.resolve()
    version = _metadata_version(root)
    _validate_tag(version, tag)
    artifacts = _validate_artifacts((dist or root / "dist").resolve(), version)
    return ReleaseReport(version, artifacts)


def _build_parser() -> argparse.ArgumentParser:
    script_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Validate package metadata and release artifacts before publication"
    )
    parser.add_argument("--root", type=Path, default=script_root)
    parser.add_argument("--dist", type=Path, default=None)
    parser.add_argument("--tag", help="tag being published, for example v0.1.0")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        report = validate_release(args.root, args.dist, tag=args.tag)
    except (OSError, ReleaseCheckError) as exc:
        print(f"release check failed: {exc}", file=sys.stderr)
        return 1

    print(f"release metadata: version={report.version}")
    for artifact in report.artifacts:
        print(
            f"{artifact.kind}: {artifact.name} ({artifact.size} bytes, "
            f"sha256={artifact.sha256})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
