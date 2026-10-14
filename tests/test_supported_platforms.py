"""Keep the Python versions the package claims equal to the versions CI tests.

`requires-python` is open-ended, so the claim a user can check is the list of
classifiers. CI must test every one of them on every platform, and nothing it
does not test may be listed (R32).
"""

from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"
PYPROJECT = ROOT / "pyproject.toml"


def _matrix_list(key: str) -> list[str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(rf"^\s+{key}: \[(.*)\]\s*$", text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"test.yml has no inline matrix list for {key!r}")
    return [entry.strip().strip("\"'") for entry in match.group(1).split(",")]


class SupportedPlatformTests(unittest.TestCase):
    def test_ci_tests_exactly_the_classified_python_versions(self) -> None:
        project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
        prefix = "Programming Language :: Python :: 3."
        classified = [
            "3." + classifier[len(prefix) :]
            for classifier in project["classifiers"]
            if classifier.startswith(prefix)
        ]
        self.assertEqual(sorted(_matrix_list("python")), sorted(classified))

    def test_lowest_classified_version_is_the_required_minimum(self) -> None:
        project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
        minimum = project["requires-python"].removeprefix(">=")
        versions = sorted(
            _matrix_list("python"), key=lambda v: tuple(map(int, v.split(".")))
        )
        self.assertEqual(versions[0], minimum)

    def test_ci_runs_on_linux_windows_and_macos(self) -> None:
        self.assertEqual(
            sorted(_matrix_list("os")),
            ["macos-latest", "ubuntu-latest", "windows-latest"],
        )


if __name__ == "__main__":
    unittest.main()
