"""Deterministic byte and token-efficiency measurements for local backlog commands.

The benchmark deliberately measures serialized payloads rather than wall-clock
time.  Runtime measurements are sensitive to the host and are not useful as a
context-size regression signal.  The fixture and JSON serializer are stable so
that the same commit produces the same byte counts in local development and CI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from .manifest import validate_manifest
from .priority import prioritize, select_next
from .sprint import plan_sprint, sprint_plan_payload
from .sync import build_sync_plan, render_issue_body


BACKLOG_SIZES = (100, 1_000, 10_000)
OPERATIONS = (
    "summary",
    "show",
    "next",
    "prioritize",
    "sprint-plan",
    "sprint-plan-compact",
    "snapshot",
    "sync-plan",
)
GENERATOR_VERSION = "r09-representative-v1"
PRIORITIZE_LIMIT = 20
SPRINT_CAPACITY = 20
SPRINT_NAME = "Benchmark Sprint"

# Budgets are expressed as a fixed envelope plus a per-item allowance.  The
# fixed-size commands should stay bounded as the backlog grows.  Snapshots and
# full cold-sync plans are disposable cache artifacts, so their budgets scale
# linearly with the number of items and protect against accidental field bloat.
OUTPUT_BUDGETS: dict[str, dict[str, int]] = {
    "summary": {"base_bytes": 512, "per_item_bytes": 0},
    "show": {"base_bytes": 1_024, "per_item_bytes": 0},
    "next": {"base_bytes": 512, "per_item_bytes": 0},
    "prioritize": {"base_bytes": 6_144, "per_item_bytes": 0},
    "sprint-plan": {"base_bytes": 8_192, "per_item_bytes": 58},
    "sprint-plan-compact": {"base_bytes": 8_192, "per_item_bytes": 0},
    "snapshot": {"base_bytes": 16_384, "per_item_bytes": 900},
    "sync-plan": {"base_bytes": 16_384, "per_item_bytes": 750},
}
# A short alias makes the public contract easy to discover for callers that
# want to report the documented budgets alongside their measurements.
BUDGETS = OUTPUT_BUDGETS


def _validate_size(item_count: int) -> int:
    if isinstance(item_count, bool) or not isinstance(item_count, int):
        raise ValueError("item_count must be a positive integer")
    if item_count < 1:
        raise ValueError("item_count must be a positive integer")
    return item_count


def _item_id(index: int, width: int = 5) -> str:
    return f"T-{index:0{width}d}"


def representative_manifest(item_count: int) -> dict[str, Any]:
    """Build a valid, deterministic manifest with ``item_count`` work items.

    The fixture has a small, shallow dependency fan-out and a mix of statuses,
    maturity values, types, and sprint assignments.  Dependencies intentionally
    point to two stable roots instead of forming a long chain, keeping the
    fixture representative without making validation depend on Python's
    recursion limit at 10,000 items.
    """

    count = _validate_size(item_count)
    width = max(5, len(str(count)))
    statuses = [
        "Inbox",
        "Refining",
        "Ready",
        "Planned",
        "In Progress",
        "In Review",
        "Done",
        "Blocked",
    ]
    items: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        item_id = _item_id(index, width)
        if index <= 2:
            status = "Ready"
        elif index % 19 == 0:
            status = "Done"
        elif index % 23 == 0:
            status = "Blocked"
        elif index % 17 == 0:
            status = "Refining"
        else:
            status = "Ready"

        dependency: list[str] = []
        if index > 3 and index % 7 == 0:
            dependency = [_item_id(1, width)]
        elif index > 3 and index % 11 == 0:
            dependency = [_item_id(2, width)]

        item_type = ("Task", "Story", "Bug")[(index - 1) % 3]
        items.append(
            {
                "id": item_id,
                "title": f"Benchmark work item {index:0{width}d}",
                "type": item_type,
                "description": (
                    f"Deliver the deterministic outcome for synthetic backlog "
                    f"item {index:0{width}d}."
                ),
                "acceptance_criteria": [
                    f"Synthetic item {item_id} is complete and verified."
                ],
                "parent": None,
                "depends_on": dependency,
                "impact": (index % 5) + 1,
                "effort": (index % 5) + 1,
                "business_value": ((index * 3) % 5) + 1,
                "enabler_value": index % 6,
                "status": status,
                "maturity": "refined" if index % 29 == 0 else "ready",
                "sprint": SPRINT_NAME if index % 5 == 0 else None,
            }
        )

    # Keep the date fixed: using date.today() would make an otherwise identical
    # benchmark change at midnight and would invalidate its regression digest.
    manifest = {
        "schema_version": 1,
        "github": {
            "owner": "aegolius-labs",
            "repository": "benchmark",
            "project_number": 1,
            "issue_type_mode": "native_or_label",
        },
        "workflow": {
            "hierarchy": [
                ["Initiative"],
                ["Epic"],
                ["Feature"],
                ["Story", "Bug"],
                ["Task"],
            ],
            "statuses": statuses,
            "done_statuses": ["Done"],
            "work_item_types": ["Story", "Bug", "Task"],
            "default_capacity": SPRINT_CAPACITY,
            "iteration": {
                "field": "Sprint",
                "start_date": "2026-01-05",
                "duration_days": 14,
            },
        },
        "scoring": {
            "weights": {
                "impact": 2.0,
                "business_value": 2.0,
                "enabler_value": 1.0,
                "effort": 1.0,
            },
            "dependency_boost": 0.25,
        },
        "items": items,
    }
    return validate_manifest(manifest)


def representative_snapshot(
    manifest: Mapping[str, Any],
    *,
    scores: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Build a deterministic GitHub-shaped snapshot for a generated manifest."""

    data = validate_manifest(dict(manifest))
    if scores is None:
        scores = {entry.id: entry.priority_score for entry in prioritize(data)}

    issues: list[dict[str, Any]] = []
    width = max(5, len(str(len(data["items"]))))
    for index, item in enumerate(data["items"], start=1):
        item_id = item["id"]
        issue_type = item["type"]
        issues.append(
            {
                "abk_id": item_id,
                "number": index,
                "id": 100_000 + index,
                "node_id": f"NODE_{index:0{width}d}",
                "url": f"https://github.com/aegolius-labs/benchmark/issues/{index}",
                "title": item["title"],
                "body": render_issue_body(item),
                "type": issue_type,
                "labels": ["area:benchmark", f"type:{issue_type.lower()}"],
                "state": "closed" if item["status"] == "Done" else "open",
                "in_project": True,
                "project_item_id": f"PVTI_{index:0{width}d}",
                "project_fields": {
                    "Status": item["status"],
                    "Impact": item["impact"],
                    "Effort": item["effort"],
                    "Business Value": item["business_value"],
                    "Enabler Value": item["enabler_value"],
                    "Priority": scores[item_id],
                    **({"Sprint": item["sprint"]} if item.get("sprint") else {}),
                },
                "parent_abk_id": item["parent"],
                "depends_on_abk_ids": list(item["depends_on"]),
            }
        )
    return {
        "schema_version": 1,
        "github": {
            "owner": "aegolius-labs",
            "repository": "benchmark",
            "project_number": 1,
        },
        "issues": issues,
    }


def serialize_json(value: Any, *, pretty: bool = False) -> bytes:
    """Serialize a payload as deterministic UTF-8 JSON with one trailing newline."""

    if pretty:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    else:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return (text + "\n").encode("utf-8")


def estimated_tokens(payload: bytes | str) -> int:
    """Return a stable, tokenizer-free token estimate based on UTF-8 bytes.

    Four bytes per token is a common planning approximation for JSON.  The
    exact byte count remains the authoritative regression signal because this
    estimate is intentionally independent of any model tokenizer or package.
    """

    byte_count = len(payload.encode("utf-8") if isinstance(payload, str) else payload)
    return (byte_count + 3) // 4


def budget_for(operation: str, item_count: int) -> dict[str, int]:
    """Return the byte and estimated-token budget for one operation and size."""

    count = _validate_size(item_count)
    try:
        spec = OUTPUT_BUDGETS[operation]
    except KeyError as exc:
        raise ValueError(f"Unknown benchmark operation: {operation}") from exc
    max_bytes = spec["base_bytes"] + spec["per_item_bytes"] * count
    return {
        "max_bytes": max_bytes,
        "max_estimated_tokens": (max_bytes + 3) // 4,
    }


def _summary_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for item in data["items"]:
        by_type[item["type"]] = by_type.get(item["type"], 0) + 1
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
    return {
        "items": len(data["items"]),
        "by_type": dict(sorted(by_type.items())),
        "by_status": dict(sorted(by_status.items())),
    }


def _measurement(
    operation: str,
    item_count: int,
    payload: Any,
    *,
    records: int,
) -> dict[str, Any]:
    compact = serialize_json(payload)
    pretty = serialize_json(payload, pretty=True)
    return {
        "operation": operation,
        "items": item_count,
        "records": records,
        "bytes": len(compact),
        "estimated_tokens": estimated_tokens(compact),
        "pretty_bytes": len(pretty),
        "pretty_estimated_tokens": estimated_tokens(pretty),
        "sha256": hashlib.sha256(compact).hexdigest(),
    }


def benchmark(sizes: Sequence[int] = BACKLOG_SIZES) -> dict[str, Any]:
    """Measure all compact local operations for each requested backlog size."""

    normalized_sizes = tuple(_validate_size(size) for size in sizes)
    if not normalized_sizes:
        raise ValueError("At least one benchmark size is required")

    runs: list[dict[str, Any]] = []
    for item_count in normalized_sizes:
        data = representative_manifest(item_count)
        scored = prioritize(data)
        score_by_id = {entry.id: entry.priority_score for entry in scored}
        snapshot = representative_snapshot(data, scores=score_by_id)

        show_id = _item_id((item_count + 1) // 2, max(5, len(str(item_count))))
        show_item = next(item for item in data["items"] if item["id"] == show_id)
        show_score = next(entry for entry in scored if entry.id == show_id)
        next_item = select_next(data)
        priority_payload = {
            "count": len(scored[:PRIORITIZE_LIMIT]),
            "items": [asdict(entry) for entry in scored[:PRIORITIZE_LIMIT]],
        }
        sprint_plan = plan_sprint(data, capacity=SPRINT_CAPACITY, sprint=SPRINT_NAME)
        sprint_payload = sprint_plan_payload(sprint_plan)
        compact_sprint_payload = sprint_plan_payload(
            sprint_plan,
            skipped_limit=50,
        )
        sync_payload = build_sync_plan(data, {"issues": []}).as_dict()

        payloads: dict[str, tuple[Any, int]] = {
            "summary": (_summary_payload(data), 1),
            "show": ({"item": show_item, "scores": asdict(show_score)}, 1),
            "next": ({"item": asdict(next_item) if next_item else None}, 1),
            "prioritize": (priority_payload, len(priority_payload["items"])),
            "sprint-plan": (sprint_payload, len(sprint_payload["items"])),
            "sprint-plan-compact": (
                compact_sprint_payload,
                len(compact_sprint_payload["items"]),
            ),
            "snapshot": (snapshot, len(snapshot["issues"])),
            "sync-plan": (sync_payload, sync_payload["action_count"]),
        }
        measurements = {
            operation: _measurement(
                operation,
                item_count,
                payload,
                records=records,
            )
            for operation, (payload, records) in payloads.items()
        }
        runs.append(
            {
                "items": item_count,
                "measurements": measurements,
            }
        )

    result: dict[str, Any] = {
        "schema_version": 1,
        "generator": GENERATOR_VERSION,
        "sizes": list(normalized_sizes),
        "operations": list(OPERATIONS),
        "budgets": {
            operation: {
                "base_bytes": spec["base_bytes"],
                "per_item_bytes": spec["per_item_bytes"],
            }
            for operation, spec in OUTPUT_BUDGETS.items()
        },
        "runs": runs,
    }
    failures = assert_budgets(result)
    result["within_budget"] = not failures
    result["budget_failures"] = failures
    return result


def assert_budgets(result: Mapping[str, Any]) -> list[str]:
    """Return human-readable budget failures without depending on timing."""

    failures: list[str] = []
    for run in result.get("runs", []):
        item_count = run.get("items")
        measurements = run.get("measurements", {})
        if not isinstance(item_count, int) or not isinstance(measurements, Mapping):
            failures.append("malformed benchmark run")
            continue
        for operation, measurement in measurements.items():
            if operation not in OUTPUT_BUDGETS:
                failures.append(f"{item_count} items {operation}: unknown operation")
                continue
            if not isinstance(measurement, Mapping):
                failures.append(f"{item_count} items {operation}: malformed measurement")
                continue
            actual = measurement.get("bytes")
            budget = budget_for(operation, item_count)
            limit = budget["max_bytes"]
            if not isinstance(actual, int):
                failures.append(f"{item_count} items {operation}: missing byte count")
            elif actual > limit:
                failures.append(
                    f"{item_count} items {operation}: {actual} bytes exceeds {limit}"
                )
            actual_tokens = measurement.get("estimated_tokens")
            token_limit = budget["max_estimated_tokens"]
            if not isinstance(actual_tokens, int):
                failures.append(
                    f"{item_count} items {operation}: missing estimated token count"
                )
            elif actual_tokens > token_limit:
                failures.append(
                    f"{item_count} items {operation}: {actual_tokens} estimated tokens "
                    f"exceeds {token_limit}"
                )
    return failures


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description="Measure deterministic backlog command payload sizes",
    )
    parser.add_argument(
        "--size",
        type=int,
        action="append",
        dest="sizes",
        help="Backlog size to measure (repeatable; defaults to 100, 1000, 10000)",
    )
    parser.add_argument(
        "--output",
        help="Write the full JSON report to this path instead of stdout",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when a documented byte budget is exceeded",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = benchmark(tuple(args.sizes) if args.sizes else BACKLOG_SIZES)
    except ValueError as exc:
        _parser().error(str(exc))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(serialize_json(result, pretty=True))
        print(
            json.dumps(
                {
                    "output": str(output_path),
                    "within_budget": result["within_budget"],
                    "budget_failures": result["budget_failures"],
                },
                indent=2,
            )
        )
    else:
        sys.stdout.buffer.write(serialize_json(result, pretty=True))

    return 0 if not args.check or result["within_budget"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
