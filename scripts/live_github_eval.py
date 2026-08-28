from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(SOURCE_ROOT))

from evals.live_github.harness import (  # noqa: E402
    FIXTURE_PATH,
    VARIANTS,
    materialize_manifest,
    prepare_suite,
    run_suite,
    verify_evidence,
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="live-github-eval",
        description=(
            "Prepare and verify disposable live-GitHub evaluation evidence. "
            "This harness never contacts or mutates GitHub."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="Create an offline evaluation session")
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--owner", required=True)
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--iteration-start", required=True)
    prepare.add_argument("--backend", choices=("gh", "api", "mcp"), required=True)

    show = commands.add_parser("show", help="Render the semantic execution plan")
    show.add_argument("--suite", required=True)

    materialize = commands.add_parser(
        "materialize",
        help="Bind a created Project number and stage an empty ingestion manifest",
    )
    materialize.add_argument("--suite", required=True)
    materialize.add_argument("--variant", choices=VARIANTS, required=True)
    materialize.add_argument("--project-number", type=int, required=True)

    verify = commands.add_parser("verify", help="Verify a complete evidence bundle")
    verify.add_argument("--suite", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepare":
        output = Path(args.output)
        suite = prepare_suite(
            output,
            owner=args.owner,
            run_id=args.run_id,
            iteration_start=args.iteration_start,
            backend=args.backend,
        )
        print(
            json.dumps(
                {
                    "suite": str(output / "suite.json"),
                    "mutation_authorized": False,
                    "execution_confirmation": suite["execution_confirmation"],
                    "cleanup_confirmation": suite["cleanup_confirmation"],
                    "resources": [
                        {
                            "variant": value["name"],
                            "repository": value["repository"],
                            "project_title": value["project_title"],
                        }
                        for value in suite["variants"]
                    ],
                },
                indent=2,
            )
        )
        return 0

    suite_path = Path(args.suite)
    suite = _read_json(suite_path)
    root = suite_path.parent
    if args.command == "show":
        print(json.dumps(run_suite(suite), indent=2))
        return 0
    if args.command == "materialize":
        variant = next(
            value for value in suite["variants"] if value["name"] == args.variant
        )
        template = _read_json(FIXTURE_PATH)
        expected = materialize_manifest(
            template,
            owner=suite["owner"],
            repository=variant["repository"],
            project_number=args.project_number,
            issue_type_mode=variant["issue_type_mode"],
            iteration_start=suite["iteration_start"],
        )
        actual = copy.deepcopy(expected)
        actual["items"] = []
        evidence_root = root / args.variant / "evidence"
        _write_json(evidence_root / "expected-manifest.json", expected)
        _write_json(evidence_root / "manifest.json", actual)
        print(
            json.dumps(
                {
                    "manifest": str(evidence_root / "manifest.json"),
                    "expected_manifest": str(evidence_root / "expected-manifest.json"),
                    "items_to_ingest": len(expected["items"]),
                    "network_access": False,
                },
                indent=2,
            )
        )
        return 0
    if args.command == "verify":
        report = verify_evidence(root, suite)
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
