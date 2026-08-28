from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from agentic_backlog_kit.manifest import validate_manifest
from agentic_backlog_kit.priority import prioritize
from agentic_backlog_kit.sprint import plan_sprint


HERE = Path(__file__).resolve().parent
FIXTURE_PATH = HERE / "fixtures" / "manifest.template.json"
EXPECTED_STATE_PATH = HERE / "expected-state.json"
EVIDENCE_CONTRACT_PATH = HERE / "evidence-contract.json"
VARIANTS = ("native", "labels")
BACKENDS = ("gh", "api", "mcp")
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class EvaluationSafetyError(RuntimeError):
    """Raised when an evaluation operation is not explicitly authorized."""


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


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def resource_names(run_id: str, variant: str) -> dict[str, str]:
    """Return stable disposable resource names for one caller-supplied run ID."""

    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of: {', '.join(VARIANTS)}")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must be a non-empty string")
    normalized = re.sub(r"[^a-z0-9]+", "-", run_id.strip().lower()).strip("-")
    normalized = normalized[:32].rstrip("-") or "run"
    suffix = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8]
    token = f"{normalized}-{suffix}"
    repository = f"abk-eval-{token}-{variant}"
    if len(repository) > 100:
        repository = repository[:100].rstrip("-")
    return {
        "token": token,
        "repository": repository,
        "project_title": f"ABK Eval {token} [{variant}]",
    }


def materialize_manifest(
    template: Mapping[str, Any],
    *,
    owner: str,
    repository: str,
    project_number: int,
    issue_type_mode: str,
    iteration_start: str,
) -> dict[str, Any]:
    """Fill live identities into the checked-in fixture and validate the result."""

    data = copy.deepcopy(dict(template))
    data["github"] = {
        "owner": owner,
        "repository": repository,
        "project_number": project_number,
        "issue_type_mode": issue_type_mode,
    }
    data["workflow"]["iteration"]["start_date"] = iteration_start
    return validate_manifest(data)


def _steps() -> list[dict[str, Any]]:
    # These are semantic checkpoints. The Wave C operator maps them through the
    # selected backend and uses the core engine's digest for every apply step.
    return [
        {"id": "preflight", "mutates": False, "confirmation": None},
        {
            "id": "resource-create",
            "mutates": True,
            "confirmation": "reviewed-plan-digest",
        },
        {"id": "bootstrap-plan", "mutates": False, "confirmation": None},
        {
            "id": "bootstrap-apply",
            "mutates": True,
            "confirmation": "reviewed-plan-digest",
        },
        {"id": "scaffold-snapshot", "mutates": False, "confirmation": None},
        {"id": "scaffold-plan", "mutates": False, "confirmation": None},
        {
            "id": "scaffold-apply",
            "mutates": True,
            "confirmation": "reviewed-plan-digest",
        },
        {"id": "ingest-local", "mutates": False, "confirmation": None},
        {"id": "prioritize", "mutates": False, "confirmation": None},
        {"id": "sprint-plan", "mutates": False, "confirmation": None},
        {"id": "iteration-lifecycle-plan", "mutates": False, "confirmation": None},
        {
            "id": "iteration-lifecycle-apply",
            "mutates": True,
            "confirmation": "reviewed-plan-digest",
        },
        {"id": "sync-snapshot", "mutates": False, "confirmation": None},
        {"id": "sync-plan", "mutates": False, "confirmation": None},
        {
            "id": "sync-apply",
            "mutates": True,
            "confirmation": "reviewed-plan-digest",
        },
        {"id": "post-apply-verify", "mutates": False, "confirmation": None},
        {"id": "second-plans-zero", "mutates": False, "confirmation": None},
        {"id": "evidence-verify", "mutates": False, "confirmation": None},
    ]


def _backend_matrix() -> dict[str, Any]:
    return {
        "gh": {
            "transport": "GitHub CLI",
            "preflight": [
                "gh --version",
                "gh auth status",
                "Confirm repository and organization Project write permissions",
            ],
            "engine_backend": "--backend gh",
            "notes": "Use gh for resource setup and the engine's GraphQL/REST transport.",
        },
        "api": {
            "transport": "Direct GitHub GraphQL and REST APIs",
            "preflight": [
                "Confirm GH_TOKEN or GITHUB_TOKEN is present without recording it",
                "Query viewer identity and required repository/Project permissions",
            ],
            "engine_backend": "--backend api",
            "notes": "Never record Authorization headers or token values in evidence.",
        },
        "mcp": {
            "transport": "GitHub MCP tools",
            "preflight": [
                "Confirm the GitHub MCP connection identity",
                "Confirm repository, issue, and Project capabilities before mutation",
            ],
            "engine_backend": "snapshot files produced by MCP; local planning remains authoritative",
            "notes": (
                "The agent translates MCP reads into canonical snapshot files, reviews local "
                "plan digests, performs equivalent MCP writes one action at a time, then refreshes."
            ),
        },
    }


def prepare_suite(
    output_root: Path,
    *,
    owner: str,
    run_id: str,
    iteration_start: str,
    backend: str,
) -> dict[str, Any]:
    """Prepare a deterministic evaluation session without network access or writes."""

    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("owner must be a non-empty GitHub organization login")
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of: {', '.join(BACKENDS)}")
    template = _read_json(FIXTURE_PATH)
    expected = _read_json(EXPECTED_STATE_PATH)
    contract = _read_json(EVIDENCE_CONTRACT_PATH)
    variants: list[dict[str, Any]] = []
    for mode in VARIANTS:
        names = resource_names(run_id, mode)
        seed_manifest = materialize_manifest(
            template,
            owner=owner,
            repository=names["repository"],
            project_number=1,
            issue_type_mode=mode,
            iteration_start=iteration_start,
        )
        ranking = [entry.id for entry in prioritize(seed_manifest)]
        sprint = plan_sprint(seed_manifest, sprint="Sprint 1")
        entry = {
            "name": mode,
            **names,
            "issue_type_mode": mode,
            "project_number_pending": True,
            "expected_item_ids": [item["id"] for item in seed_manifest["items"]],
            "expected_priority_ids": ranking,
            "expected_sprint_ids": [item.id for item in sprint.items],
        }
        variants.append(entry)
        variant_root = output_root / mode
        _write_json(variant_root / "seed-manifest.json", seed_manifest)
        _write_json(variant_root / "expected-state.json", expected)
        for index, item in enumerate(seed_manifest["items"], start=1):
            _write_json(
                variant_root / "ingestion-items" / f"{index:02d}-{item['id']}.json",
                item,
            )

    coverage = [
        "bootstrap",
        "scaffold",
        "ingestion",
        "prioritization",
        "sprint_planning",
        "sync_apply_verify",
        "second_plan_zero",
        "hierarchy",
        "dependencies",
        "fields",
        "iterations",
        "views",
        "native_issue_types",
        "label_fallback",
    ]
    base: dict[str, Any] = {
        "schema_version": 1,
        "suite": "agentic-backlog-kit-live-github",
        "owner": owner,
        "run_id": run_id,
        "selected_backend": backend,
        "iteration_start": iteration_start,
        "mutation_authorized": False,
        "coverage": coverage,
        "backend_matrix": _backend_matrix(),
        "steps": _steps(),
        "cleanup_steps": [
            {
                "id": "delete-disposable-project",
                "mutates": True,
                "confirmation": "separate-cleanup-digest",
            },
            {
                "id": "delete-disposable-repository",
                "mutates": True,
                "confirmation": "separate-cleanup-digest",
            },
        ],
        "variants": variants,
        "evidence_contract": contract,
    }
    execution_confirmation = _digest({"operation": "execute", "suite": base})
    cleanup_confirmation = _digest(
        {
            "operation": "cleanup",
            "execution_confirmation": execution_confirmation,
            "resources": [
                {
                    "repository": variant["repository"],
                    "project_title": variant["project_title"],
                }
                for variant in variants
            ],
        }
    )
    suite = {
        **base,
        "execution_confirmation": execution_confirmation,
        "cleanup_confirmation": cleanup_confirmation,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "suite.json", suite)
    return suite


def run_suite(
    suite: Mapping[str, Any],
    *,
    execute: bool = False,
    confirmation: str | None = None,
    reviewed_digests: Mapping[str, str] | None = None,
    runner: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Render by default; execute only through a caller-supplied, fully gated adapter."""

    steps = [copy.deepcopy(step) for step in suite.get("steps", [])]
    if not execute:
        return {"status": "dry-run", "executed": 0, "steps": steps}
    if confirmation != suite.get("execution_confirmation"):
        raise EvaluationSafetyError("Execution requires the exact evaluation digest")
    if runner is None:
        raise EvaluationSafetyError("Execution requires an explicit backend runner")
    reviewed = dict(reviewed_digests or {})
    for step in steps:
        if not step.get("mutates"):
            continue
        plan_digest = reviewed.get(str(step.get("id")))
        if not isinstance(plan_digest, str) or not HEX_DIGEST.fullmatch(plan_digest):
            raise EvaluationSafetyError(
                f"Mutating step {step.get('id')} requires its exact reviewed plan digest"
            )
        step["reviewed_plan_digest"] = plan_digest
    completed = 0
    for variant in suite.get("variants", []):
        for step in steps:
            runner({**step, "variant": variant.get("name")})
            completed += 1
    return {"status": "completed", "executed": completed}


def run_cleanup(
    suite: Mapping[str, Any],
    *,
    confirmation: str | None,
    runner: Callable[[dict[str, Any]], Any] | None,
    verified_report: Mapping[str, Any] | None = None,
    resolved_resources: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run destructive cleanup only after a distinct exact confirmation."""

    if confirmation != suite.get("cleanup_confirmation"):
        raise EvaluationSafetyError("Cleanup requires its separate exact cleanup digest")
    if runner is None:
        raise EvaluationSafetyError("Cleanup requires an explicit backend runner")
    if not isinstance(verified_report, Mapping) or verified_report.get("passed") is not True:
        raise EvaluationSafetyError("Cleanup requires a passing preserved evidence report")
    resolved = dict(resolved_resources or {})
    for variant in suite.get("variants", []):
        name = variant.get("name")
        current = resolved.get(str(name))
        if not isinstance(current, Mapping):
            raise EvaluationSafetyError(f"Cleanup requires freshly resolved {name} identities")
        if (
            current.get("owner") != suite.get("owner")
            or current.get("repository") != variant.get("repository")
            or current.get("project_title") != variant.get("project_title")
            or not current.get("project_node_id")
        ):
            raise EvaluationSafetyError(f"Cleanup identity mismatch for {name}")
    completed = 0
    for variant in suite.get("variants", []):
        for step in suite.get("cleanup_steps", []):
            runner({**copy.deepcopy(step), "variant": variant.get("name")})
            completed += 1
    return {"status": "completed", "executed": completed}


def _load_evidence(path: Path, failures: list[str]) -> dict[str, Any]:
    try:
        return _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failures.append(f"{path}: cannot read JSON evidence: {exc}")
        return {}


def _actions_are_zero(plan: Mapping[str, Any]) -> bool:
    actions = plan.get("actions")
    count = plan.get("action_count")
    return (isinstance(actions, list) and not actions) or count == 0


def _field_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        name = value.get("name")
        if isinstance(name, str):
            return name
        nested = value.get("field")
        if nested is not value:
            return _field_name(nested)
    return None


def _view_shape(view: Mapping[str, Any]) -> dict[str, Any]:
    visible = [
        name
        for name in (_field_name(value) for value in view.get("visible_fields", []))
        if name
    ]
    group = [
        name
        for name in (_field_name(value) for value in view.get("group_by", []))
        if name
    ]
    vertical = [
        name
        for name in (_field_name(value) for value in view.get("vertical_group_by", []))
        if name
    ]
    sorts: list[dict[str, str]] = []
    for value in view.get("sort_by", []):
        if not isinstance(value, Mapping):
            continue
        name = _field_name(value.get("field"))
        direction = value.get("direction")
        if name and isinstance(direction, str):
            sorts.append({"field": name, "direction": direction.lower()})
    return {
        "name": view.get("name"),
        "layout": str(view.get("layout", "")).lower(),
        "filter": view.get("filter") or "",
        "visible_fields": visible,
        "group_by": group,
        "vertical_group_by": vertical,
        "sort_by": sorts,
    }


def _assert_scaffold(
    snapshot: Mapping[str, Any], expected: Mapping[str, Any], failures: list[str]
) -> None:
    fields = {
        field.get("name"): field
        for field in snapshot.get("fields", [])
        if isinstance(field, Mapping)
    }
    for wanted in expected.get("fields", []):
        current = fields.get(wanted.get("name"))
        if current is None:
            failures.append(f"missing Project field {wanted.get('name')}")
            continue
        data_type = current.get("data_type") or current.get("dataType")
        if data_type != wanted.get("data_type"):
            failures.append(
                f"Project field {wanted.get('name')} has {data_type}; expected {wanted.get('data_type')}"
            )
    views = {
        view.get("name"): view
        for view in snapshot.get("views", [])
        if isinstance(view, Mapping)
    }
    for wanted in expected.get("views", []):
        current = views.get(wanted.get("name"))
        if current is None:
            failures.append(f"missing Project view {wanted.get('name')}")
        elif _view_shape(current) != _view_shape(wanted):
            failures.append(f"Project view {wanted.get('name')} configuration differs")
    label_names = {
        label.get("name")
        for label in snapshot.get("labels", [])
        if isinstance(label, Mapping)
    }
    missing_labels = set(expected.get("required_type_labels", [])) - label_names
    if missing_labels:
        failures.append(f"missing fallback labels: {', '.join(sorted(missing_labels))}")


def _assert_iterations(
    snapshot: Mapping[str, Any], expected: Mapping[str, Any], failures: list[str]
) -> None:
    wanted = expected.get("iterations", {})
    sprint = next(
        (
            field
            for field in snapshot.get("fields", [])
            if isinstance(field, Mapping) and field.get("name") == wanted.get("field")
        ),
        None,
    )
    if not isinstance(sprint, Mapping):
        failures.append("iteration field is missing")
        return
    configuration = sprint.get("iteration_configuration")
    if not isinstance(configuration, Mapping):
        failures.append("iteration field configuration is missing")
        return
    if configuration.get("duration_days") != wanted.get("duration_days"):
        failures.append("iteration duration differs from the expected cadence")
    active = configuration.get("iterations", [])
    completed = configuration.get("completed_iterations", [])
    if not isinstance(active, list) or not isinstance(completed, list):
        failures.append("active/completed iteration definitions are malformed")
        return
    by_title = {
        value.get("title"): value for value in active if isinstance(value, Mapping)
    }
    for title in wanted.get("required_active_titles", []):
        value = by_title.get(title)
        if value is None:
            failures.append(f"missing active iteration {title}")
        elif not value.get("id") or value.get("completed") is True:
            failures.append(f"active iteration {title} has invalid identity/state")


def _assert_receipt(
    plan: Mapping[str, Any], receipt: Mapping[str, Any], label: str, failures: list[str]
) -> None:
    digest = plan.get("digest")
    if not isinstance(digest, str) or not HEX_DIGEST.fullmatch(digest):
        failures.append(f"{label} plan digest is malformed")
    if receipt.get("status") != "completed":
        failures.append(f"{label} receipt is not completed")
    if receipt.get("plan_digest") != digest:
        failures.append(f"{label} receipt does not bind the reviewed plan digest")
    completed = receipt.get("completed_actions")
    total = receipt.get("total_actions")
    applied = receipt.get("applied_actions")
    if not isinstance(completed, list):
        failures.append(f"{label} receipt lacks its completed-action journal")
    elif applied != len(completed) or total != applied:
        failures.append(f"{label} receipt action counts do not describe a completed plan")


def _issue_type(issue: Mapping[str, Any]) -> str | None:
    value = issue.get("type")
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping) and isinstance(value.get("name"), str):
        return value["name"]
    return None


def _assert_issues(
    snapshot: Mapping[str, Any], manifest: Mapping[str, Any], mode: str, failures: list[str]
) -> None:
    priorities = {value.id: value.priority_score for value in prioritize(dict(manifest))}
    remote = {
        issue.get("abk_id"): issue
        for issue in snapshot.get("issues", [])
        if isinstance(issue, Mapping)
    }
    for item in manifest.get("items", []):
        item_id = item["id"]
        issue = remote.get(item_id)
        if issue is None:
            failures.append(f"missing managed issue {item_id}")
            continue
        if issue.get("parent_abk_id") != item.get("parent"):
            failures.append(f"managed issue {item_id} has incorrect parent")
        if issue.get("depends_on_abk_ids", []) != item.get("depends_on", []):
            failures.append(f"managed issue {item_id} has incorrect dependencies")
        fields = issue.get("project_fields", {})
        if not isinstance(fields, Mapping) or fields.get("Status") != item.get("status"):
            failures.append(f"managed issue {item_id} has incorrect Status field")
            fields = {}
        for manifest_name, project_name in (
            ("impact", "Impact"),
            ("effort", "Effort"),
            ("business_value", "Business Value"),
            ("enabler_value", "Enabler Value"),
        ):
            if fields.get(project_name) != item.get(manifest_name):
                failures.append(
                    f"managed issue {item_id} has incorrect {project_name} field"
                )
        if fields.get("Priority") != priorities[item_id]:
            failures.append(f"managed issue {item_id} has incorrect Priority field")
        if item.get("sprint") and fields.get("Sprint") != item.get("sprint"):
            failures.append(f"managed issue {item_id} has incorrect Sprint field")
        fallback = f"type:{str(item.get('type')).lower()}"
        labels = issue.get("labels", [])
        if mode == "native" and _issue_type(issue) != item.get("type"):
            failures.append(f"managed issue {item_id} has incorrect native issue type")
        managed_type_labels = [
            value for value in labels if isinstance(value, str) and value.startswith("type:")
        ]
        if mode == "native" and managed_type_labels:
            failures.append(f"managed issue {item_id} unexpectedly uses a fallback type label")
        if mode == "labels" and fallback not in labels:
            failures.append(f"managed issue {item_id} lacks fallback label {fallback}")
        if mode == "labels" and managed_type_labels != [fallback]:
            failures.append(f"managed issue {item_id} has conflicting fallback type labels")


def _assert_command_log(path: Path, label: str, failures: list[str]) -> None:
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    except OSError as exc:
        failures.append(f"{label}: cannot read commands.ndjson: {exc}")
        return
    if not lines:
        failures.append(f"{label}: commands.ndjson is empty")
        return
    forbidden = ("authorization:", "gh_token=", "github_token=", "bearer ")
    for index, line in enumerate(lines, start=1):
        if any(value in line.lower() for value in forbidden):
            failures.append(f"{label}: commands.ndjson line {index} may contain a secret")
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append(f"{label}: commands.ndjson line {index} is invalid JSON: {exc}")
            continue
        if not isinstance(value, Mapping) or value.get("redacted") is not True:
            failures.append(f"{label}: commands.ndjson line {index} lacks redacted=true")


def _verify_variant(
    root: Path,
    suite: Mapping[str, Any],
    variant: Mapping[str, Any],
) -> dict[str, Any]:
    name = str(variant.get("name"))
    variant_root = root / name / "evidence"
    failures: list[str] = []
    required = suite.get("evidence_contract", {}).get("required_per_variant", [])
    for relative in required:
        if not (variant_root / relative).is_file():
            failures.append(f"{name}: missing evidence {relative}")
    if failures:
        return {"name": name, "passed": False, "failures": failures}

    _assert_command_log(variant_root / "commands.ndjson", name, failures)

    manifest = _load_evidence(variant_root / "manifest.json", failures)
    manifest_valid = False
    try:
        manifest = validate_manifest(manifest)
    except Exception as exc:
        failures.append(f"{name}: manifest evidence is invalid: {exc}")
    else:
        manifest_valid = True
        github = manifest["github"]
        if github.get("owner") != suite.get("owner"):
            failures.append(f"{name}: manifest owner differs from the suite")
        if github.get("repository") != variant.get("repository"):
            failures.append(f"{name}: manifest repository differs from the suite")
        if github.get("issue_type_mode") != variant.get("issue_type_mode"):
            failures.append(f"{name}: manifest issue type mode differs from the suite")

    preflight = _load_evidence(variant_root / "preflight.json", failures)
    if preflight.get("passed") is not True:
        failures.append(f"{name}: preflight did not pass")
    if preflight.get("backend") != suite.get("selected_backend"):
        failures.append(f"{name}: preflight backend differs from the selected backend")
    if preflight.get("redactions_confirmed") is not True:
        failures.append(f"{name}: evidence redactions were not confirmed")

    for stage in ("bootstrap", "scaffold", "sync"):
        plan = _load_evidence(variant_root / stage / "plan.json", failures)
        receipt = _load_evidence(variant_root / stage / "receipt.json", failures)
        _assert_receipt(plan, receipt, stage, failures)

    expected = _read_json(EXPECTED_STATE_PATH)
    scaffold_after = _load_evidence(variant_root / "scaffold" / "after.json", failures)
    _assert_scaffold(scaffold_after, expected, failures)
    scaffold_second = _load_evidence(
        variant_root / "scaffold" / "second-plan.json", failures
    )
    if not _actions_are_zero(scaffold_second):
        failures.append(f"{name}: second scaffold plan is not empty")

    ingestion = _load_evidence(variant_root / "ingestion" / "result.json", failures)
    ingested_ids = ingestion.get("item_ids")
    if ingested_ids != variant.get("expected_item_ids"):
        failures.append(f"{name}: ingestion result does not match the fixture IDs")

    ranking = _load_evidence(
        variant_root / "prioritization" / "result.json", failures
    )
    ranked_ids = [
        value.get("id") for value in ranking.get("items", []) if isinstance(value, Mapping)
    ]
    if ranked_ids != variant.get("expected_priority_ids"):
        failures.append(f"{name}: priority order differs from the deterministic result")

    sprint = _load_evidence(variant_root / "sprint" / "plan.json", failures)
    sprint_ids = [
        value.get("id") for value in sprint.get("items", []) if isinstance(value, Mapping)
    ]
    if sprint_ids != variant.get("expected_sprint_ids"):
        failures.append(f"{name}: sprint selection differs from the deterministic result")

    iteration_assertions = _load_evidence(
        variant_root / "iterations" / "assertions.json", failures
    )
    required_iteration_checks = [
        "current_resolved",
        "next_resolved",
        "completed_rejected",
        "duplicate_rejected",
        "overlap_rejected",
        "incomplete_metadata_rejected",
        "extension_applied",
        "server_identities_verified",
        "second_plan_zero",
    ]
    for check in required_iteration_checks:
        if iteration_assertions.get(check) is not True:
            failures.append(f"{name}: iteration assertion {check} did not pass")
    _assert_iterations(scaffold_after, expected, failures)

    sync_after = _load_evidence(variant_root / "sync" / "after.json", failures)
    if manifest_valid:
        _assert_issues(sync_after, manifest, name, failures)
    sync_second = _load_evidence(variant_root / "sync" / "second-plan.json", failures)
    if not _actions_are_zero(sync_second):
        failures.append(f"{name}: second sync plan is not empty")

    assertions = _load_evidence(variant_root / "assertions.json", failures)
    if assertions.get("passed") is not True:
        failures.append(f"{name}: operator assertion summary did not pass")
    return {"name": name, "passed": not failures, "failures": failures}


def verify_evidence(root: Path, suite: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the complete, redacted evidence bundle without network access."""

    variants = [
        _verify_variant(root, suite, value)
        for value in suite.get("variants", [])
        if isinstance(value, Mapping)
    ]
    failures = [failure for value in variants for failure in value["failures"]]
    return {"passed": bool(variants) and not failures, "variants": variants, "failures": failures}
