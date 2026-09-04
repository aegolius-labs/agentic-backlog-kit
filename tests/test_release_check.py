from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.release_check import ReleaseCheckError, validate_release


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"


def _write_wheel(
    path: Path, *, metadata_version: str = VERSION, include_commercial: bool = True
) -> None:
    dist_info = f"agentic_backlog_kit-{VERSION}.dist-info"
    metadata = (
        "Metadata-Version: 2.1\n"
        "Name: agentic-backlog-kit\n"
        f"Version: {metadata_version}\n"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("agentic_backlog_kit/__init__.py", "__version__ = '0.1.0'\n")
        archive.writestr(f"{dist_info}/METADATA", metadata)
        archive.writestr(
            f"{dist_info}/entry_points.txt",
            "[console_scripts]\nabk = agentic_backlog_kit.cli:main\n",
        )
        archive.writestr(f"{dist_info}/licenses/LICENSE.md", "License\n")
        if include_commercial:
            archive.writestr(
                f"{dist_info}/licenses/COMMERCIAL.md", "Commercial terms\n"
            )


def _write_sdist(path: Path, *, include_commercial: bool = True) -> None:
    top = f"agentic_backlog_kit-{VERSION}"
    files = {
        f"{top}/pyproject.toml": b"[project]\nname='agentic-backlog-kit'\n",
        f"{top}/README.md": b"# Agentic Backlog Kit\n",
        f"{top}/LICENSE.md": b"License\n",
        f"{top}/src/agentic_backlog_kit/__init__.py": b"__version__ = '0.1.0'\n",
    }
    if include_commercial:
        files[f"{top}/COMMERCIAL.md"] = b"Commercial terms\n"
    with tarfile.open(path, "w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))


def _write_artifacts(
    directory: Path,
    *,
    metadata_version: str = VERSION,
    include_commercial: bool = True,
) -> None:
    _write_wheel(
        directory / f"agentic_backlog_kit-{VERSION}-py3-none-any.whl",
        metadata_version=metadata_version,
        include_commercial=include_commercial,
    )
    _write_sdist(
        directory / f"agentic_backlog_kit-{VERSION}.tar.gz",
        include_commercial=include_commercial,
    )


class ReleaseCheckTests(unittest.TestCase):
    def test_validates_metadata_tag_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory)
            _write_artifacts(dist)

            report = validate_release(ROOT, dist, tag="v0.1.0")

        self.assertEqual(VERSION, report.version)
        self.assertEqual(("wheel", "sdist"), tuple(item.kind for item in report.artifacts))
        self.assertTrue(all(len(item.sha256) == 64 for item in report.artifacts))

    def test_rejects_tag_that_does_not_match_package_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory)
            _write_artifacts(dist)

            with self.assertRaisesRegex(ReleaseCheckError, "does not match"):
                validate_release(ROOT, dist, tag="v0.1.1")

    def test_rejects_unexpected_stale_asset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory)
            _write_artifacts(dist)
            (dist / "notes.txt").write_text("not a release asset", encoding="utf-8")

            with self.assertRaisesRegex(ReleaseCheckError, "unexpected release assets"):
                validate_release(ROOT, dist, tag="v0.1.0")

    def test_rejects_wheel_metadata_version_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory)
            _write_artifacts(dist, metadata_version="0.1.1")

            with self.assertRaisesRegex(ReleaseCheckError, "metadata version"):
                validate_release(ROOT, dist, tag="v0.1.0")

    def test_rejects_artifacts_missing_commercial_notice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory)
            _write_artifacts(dist, include_commercial=False)

            with self.assertRaisesRegex(ReleaseCheckError, "COMMERCIAL.md"):
                validate_release(ROOT, dist, tag="v0.1.0")


if __name__ == "__main__":
    unittest.main()
