"""Require an explicit release baseline before treating a no-bump as success.

The organization workflow computes the next version from the commits since the
last release tag.  With no tag at all there is nothing to compute from, so it
produces no new tag - which is indistinguishable, to every later job, from the
legitimate case where nothing release-bearing has landed.  A release-bearing
merge then appears to succeed and publishes nothing (R14-F7).

This turns that silence into a failure.  It deliberately does **not** create a
tag: choosing where a project's version history starts is a decision with
permanent consequences for every version computed afterwards, and an automation
that guesses it is worse than one that stops.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable


VERSION_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


class ReleaseBaselineError(RuntimeError):
    """Raised when a no-bump cannot be trusted because no baseline exists."""


@dataclass(frozen=True, slots=True)
class BaselineReport:
    baseline: str | None
    released: bool
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline,
            "released": self.released,
            "reason": self.reason,
        }


def find_baseline(tags: Iterable[str]) -> str | None:
    """Return the highest semantic version tag, or None when there is none."""

    versions: list[tuple[tuple[int, int, int], str]] = []
    for tag in tags:
        match = VERSION_TAG.match(str(tag).strip())
        if match:
            versions.append(
                ((int(match[1]), int(match[2]), int(match[3])), str(tag).strip())
            )
    if not versions:
        return None
    return max(versions)[1]


def evaluate_baseline(tags: Iterable[str], *, new_tag: str | None) -> BaselineReport:
    """Decide whether an absent new tag is a real no-bump or a silent failure."""

    baseline = find_baseline(tags)
    if new_tag:
        return BaselineReport(baseline, True, f"Releasing {new_tag}.")
    if baseline is not None:
        return BaselineReport(
            baseline,
            False,
            f"No release-bearing change since {baseline}; nothing to publish.",
        )
    raise ReleaseBaselineError(
        "No release baseline exists, so the computed version would be derived "
        "from no history and nothing would be published. Create the first tag "
        "explicitly, for example 'git tag -a v0.0.0 <sha> && git push origin "
        "v0.0.0', then re-run. This check never creates a tag: where version "
        "history starts is a decision, not a default."
    )


def _repository_tags() -> list[str]:
    result = subprocess.run(
        ["git", "tag", "--list"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseBaselineError(
            f"Could not list tags: {result.stderr.strip() or 'git tag failed'}"
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail a no-bump that has no release baseline behind it"
    )
    parser.add_argument(
        "--new-tag",
        default="",
        help="The tag the version calculator produced, empty for a no-bump",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        report = evaluate_baseline(_repository_tags(), new_tag=args.new_tag)
    except ReleaseBaselineError as error:
        print(f"release baseline check failed: {error}", file=sys.stderr)
        return 1
    print(f"release baseline: {report.baseline or 'none'} - {report.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
