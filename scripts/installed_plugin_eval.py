from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evals.installed_plugin.harness import (  # noqa: E402
    EvaluationError,
    load_results,
    prepare_suite,
    run_diagnostics,
    synthetic_results,
    verify_suite,
    write_results,
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"Cannot read suite JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationError(f"Suite JSON {path} must contain an object")
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
        prog="installed-plugin-eval",
        description=(
            "Prepare and verify a local-marketplace installed-plugin evaluation. "
            "Conversation execution remains an explicit user/app step."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="Stage the plugin and local marketplace")
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--run-id", default="r06-local")
    prepare.add_argument("--plugin-root")

    show = commands.add_parser("show", help="Show the prepared corpus and next action")
    show.add_argument("--suite", required=True)

    diagnose = commands.add_parser(
        "diagnose", help="Run static pickup checks and optional safe CLI probes"
    )
    diagnose.add_argument("--suite", required=True)
    diagnose.add_argument("--run-cli", action="store_true")
    diagnose.add_argument("--executable")
    diagnose.add_argument("--output")

    synthetic = commands.add_parser(
        "synthetic", help="Write deterministic schema-valid verifier fixtures"
    )
    synthetic.add_argument("--suite", required=True)
    synthetic.add_argument("--output")

    record = commands.add_parser("record", help="Copy redacted conversation result records")
    record.add_argument("--suite", required=True)
    record.add_argument("--input", required=True)
    record.add_argument("--output")

    verify = commands.add_parser("verify", help="Verify static install and conversation evidence")
    verify.add_argument("--suite", required=True)
    verify.add_argument("--results")
    verify.add_argument("--report")
    return parser


def _suite_path(value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_file():
        raise EvaluationError(f"Suite file does not exist: {path}")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "prepare":
            suite = prepare_suite(
                Path(args.output),
                run_id=args.run_id,
                plugin_root=Path(args.plugin_root) if args.plugin_root else None,
            )
            output = Path(args.output).resolve()
            print(
                json.dumps(
                    {
                        "suite": str(output / "suite.json"),
                        "status": suite["status"],
                        "plugin": suite["plugin"],
                        "case_count": len(suite["cases"]),
                        "fresh_task_execution_required": True,
                        "personal_marketplace_modified": False,
                    },
                    indent=2,
                )
            )
            return 0

        suite_path = _suite_path(args.suite)
        suite = _read_json(suite_path)
        if args.command == "show":
            print(
                json.dumps(
                    {
                        "suite": str(suite_path),
                        "run_id": suite.get("run_id"),
                        "plugin": suite.get("plugin"),
                        "categories": suite.get("categories", []),
                        "case_count": len(suite.get("cases", [])),
                        "artifacts": suite.get("artifacts", {}),
                        "next": (
                            "Install the staged plugin from the generated local marketplace, "
                            "start a fresh task with it enabled, run every corpus case, and "
                            "record redacted results."
                        ),
                    },
                    indent=2,
                )
            )
            return 0
        if args.command == "diagnose":
            diagnostics = run_diagnostics(
                suite,
                suite_root=suite_path.parent,
                run_cli=args.run_cli,
                executable=args.executable,
            )
            output = (
                Path(args.output).resolve()
                if args.output
                else suite_path.parent / suite.get("artifacts", {}).get("diagnostics", "diagnostics.json")
            )
            _write_json(output, diagnostics)
            print(json.dumps({"diagnostics": str(output), **diagnostics}, indent=2))
            return 0 if diagnostics["passed"] else 1
        if args.command == "synthetic":
            output = (
                Path(args.output).resolve()
                if args.output
                else suite_path.parent / suite.get("artifacts", {}).get("results", "results.ndjson")
            )
            results = synthetic_results(suite)
            write_results(output, results)
            print(json.dumps({"results": str(output), "count": len(results)}, indent=2))
            return 0
        if args.command == "record":
            source = Path(args.input).resolve()
            results = load_results(source)
            output = (
                Path(args.output).resolve()
                if args.output
                else suite_path.parent / suite.get("artifacts", {}).get("results", "results.ndjson")
            )
            write_results(output, results)
            print(json.dumps({"results": str(output), "count": len(results)}, indent=2))
            return 0
        if args.command == "verify":
            report = verify_suite(
                suite_path,
                results_path=Path(args.results).resolve() if args.results else None,
                report_path=Path(args.report).resolve() if args.report else None,
            )
            print(json.dumps(report, indent=2))
            return 0 if report.get("passed") else 1
        raise AssertionError(f"Unhandled command: {args.command}")
    except EvaluationError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
