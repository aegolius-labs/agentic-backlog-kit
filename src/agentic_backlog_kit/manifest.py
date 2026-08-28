from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_HIERARCHY = (
    ("Initiative",),
    ("Epic",),
    ("Feature",),
    ("Story", "Bug"),
    ("Task",),
)
DEFAULT_STATUSES = (
    "Inbox",
    "Refining",
    "Ready",
    "Planned",
    "In Progress",
    "In Review",
    "Done",
    "Blocked",
)
DEFAULT_WORK_ITEM_TYPES = ("Story", "Bug", "Task")
DEFAULT_WEIGHTS = {
    "impact": 2.0,
    "business_value": 2.0,
    "enabler_value": 1.0,
    "effort": 1.0,
}
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ROOT_FIELDS = {"schema_version", "github", "workflow", "scoring", "items"}
GITHUB_FIELDS = {"owner", "repository", "project_number", "issue_type_mode"}
WORKFLOW_FIELDS = {
    "hierarchy",
    "statuses",
    "done_statuses",
    "work_item_types",
    "default_capacity",
    "iteration",
}
SCORING_FIELDS = {"weights", "dependency_boost"}
WEIGHT_FIELDS = set(DEFAULT_WEIGHTS)
ITEM_FIELDS = {
    "id",
    "title",
    "type",
    "description",
    "acceptance_criteria",
    "parent",
    "depends_on",
    "impact",
    "effort",
    "business_value",
    "enabler_value",
    "status",
    "maturity",
    "sprint",
}


class ManifestError(ValueError):
    """Raised when a local backlog manifest violates the product contract."""


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{path} must be an object")
    return value


def _require_nonempty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{path} must be a non-empty string")
    return value.strip()


def _reject_unknown(
    value: dict[str, Any], allowed: set[str], path: str
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ManifestError(f"{path} contains unknown fields: {unknown}")


def _validate_dimension(item: dict[str, Any], name: str, minimum: int) -> None:
    value = item.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= 5:
        raise ManifestError(
            f"Item '{item.get('id', '?')}' {name} must be an integer from {minimum} to 5"
        )


def _hierarchy_levels(hierarchy: list[list[str]] | tuple[tuple[str, ...], ...]) -> dict[str, int]:
    levels: dict[str, int] = {}
    for level, item_types in enumerate(hierarchy):
        if not isinstance(item_types, (list, tuple)) or not item_types:
            raise ManifestError("workflow.hierarchy levels must be non-empty arrays")
        for item_type in item_types:
            name = _require_nonempty_string(item_type, "workflow.hierarchy item type")
            if name in levels:
                raise ManifestError(f"Duplicate hierarchy item type '{name}'")
            levels[name] = level
    return levels


def _find_dependency_cycle(items: dict[str, dict[str, Any]]) -> list[str] | None:
    state: dict[str, int] = {item_id: 0 for item_id in items}
    stack: list[str] = []

    def visit(item_id: str) -> list[str] | None:
        state[item_id] = 1
        stack.append(item_id)
        for dependency in sorted(items[item_id]["depends_on"]):
            if state[dependency] == 0:
                cycle = visit(dependency)
                if cycle:
                    return cycle
            elif state[dependency] == 1:
                start = stack.index(dependency)
                return stack[start:] + [dependency]
        stack.pop()
        state[item_id] = 2
        return None

    for item_id in sorted(items):
        if state[item_id] == 0:
            cycle = visit(item_id)
            if cycle:
                return cycle
    return None


def validate_manifest(data: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized copy or fail before any external operation is planned."""

    root = deepcopy(_require_mapping(data, "manifest"))
    _reject_unknown(root, ROOT_FIELDS, "manifest")
    if root.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(
            f"schema_version must be {SCHEMA_VERSION}; got {root.get('schema_version')!r}"
        )

    github = _require_mapping(root.get("github"), "github")
    _reject_unknown(github, GITHUB_FIELDS, "github")
    github["owner"] = _require_nonempty_string(github.get("owner"), "github.owner")
    github["repository"] = _require_nonempty_string(
        github.get("repository"), "github.repository"
    )
    project_number = github.get("project_number")
    if isinstance(project_number, bool) or not isinstance(project_number, int) or project_number < 1:
        raise ManifestError("github.project_number must be a positive integer")
    issue_type_mode = github.setdefault("issue_type_mode", "native_or_label")
    if issue_type_mode not in {"native", "labels", "native_or_label"}:
        raise ManifestError(
            "github.issue_type_mode must be native, labels, or native_or_label"
        )

    workflow = root.setdefault("workflow", {})
    _require_mapping(workflow, "workflow")
    _reject_unknown(workflow, WORKFLOW_FIELDS, "workflow")
    hierarchy = workflow.setdefault(
        "hierarchy", [list(level) for level in DEFAULT_HIERARCHY]
    )
    if not isinstance(hierarchy, list):
        raise ManifestError("workflow.hierarchy must be an array of levels")
    levels = _hierarchy_levels(hierarchy)

    statuses = workflow.setdefault("statuses", list(DEFAULT_STATUSES))
    if not isinstance(statuses, list) or not statuses:
        raise ManifestError("workflow.statuses must be a non-empty array")
    statuses = [_require_nonempty_string(value, "workflow.statuses entry") for value in statuses]
    if len(statuses) != len(set(statuses)):
        raise ManifestError("workflow.statuses must not contain duplicates")
    workflow["statuses"] = statuses

    done_statuses = workflow.setdefault("done_statuses", ["Done"])
    if not isinstance(done_statuses, list) or not done_statuses:
        raise ManifestError("workflow.done_statuses must be a non-empty array")
    done_statuses = [
        _require_nonempty_string(value, "workflow.done_statuses entry")
        for value in done_statuses
    ]
    if len(done_statuses) != len(set(done_statuses)):
        raise ManifestError("workflow.done_statuses must not contain duplicates")
    workflow["done_statuses"] = done_statuses
    unknown_done = sorted(set(done_statuses) - set(statuses))
    if unknown_done:
        raise ManifestError(f"workflow.done_statuses contains unknown values: {unknown_done}")

    work_item_types = workflow.setdefault(
        "work_item_types", list(DEFAULT_WORK_ITEM_TYPES)
    )
    if not isinstance(work_item_types, list) or not work_item_types:
        raise ManifestError("workflow.work_item_types must be a non-empty array")
    work_item_types = [
        _require_nonempty_string(value, "workflow.work_item_types entry")
        for value in work_item_types
    ]
    if len(work_item_types) != len(set(work_item_types)):
        raise ManifestError("workflow.work_item_types must not contain duplicates")
    workflow["work_item_types"] = work_item_types
    unknown_work_types = sorted(set(work_item_types) - set(levels))
    if unknown_work_types:
        raise ManifestError(
            f"workflow.work_item_types contains unknown types: {unknown_work_types}"
        )
    capacity = workflow.setdefault("default_capacity", 20)
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
        raise ManifestError("workflow.default_capacity must be a positive integer")
    iteration = workflow.get("iteration")
    if iteration is not None:
        iteration = _require_mapping(iteration, "workflow.iteration")
        _reject_unknown(
            iteration,
            {"field", "start_date", "duration_days"},
            "workflow.iteration",
        )
        iteration["field"] = _require_nonempty_string(
            iteration.get("field"), "workflow.iteration.field"
        )
        try:
            date.fromisoformat(iteration.get("start_date"))
        except (TypeError, ValueError) as exc:
            raise ManifestError(
                "workflow.iteration.start_date must use YYYY-MM-DD"
            ) from exc
        duration = iteration.get("duration_days")
        if isinstance(duration, bool) or not isinstance(duration, int) or duration < 1:
            raise ManifestError(
                "workflow.iteration.duration_days must be a positive integer"
            )

    scoring = root.setdefault("scoring", {})
    _require_mapping(scoring, "scoring")
    _reject_unknown(scoring, SCORING_FIELDS, "scoring")
    weights = scoring.setdefault("weights", deepcopy(DEFAULT_WEIGHTS))
    _require_mapping(weights, "scoring.weights")
    _reject_unknown(weights, WEIGHT_FIELDS, "scoring.weights")
    for name, default in DEFAULT_WEIGHTS.items():
        value = weights.setdefault(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ManifestError(f"scoring.weights.{name} must be a non-negative number")
        weights[name] = float(value)
    boost = scoring.setdefault("dependency_boost", 0.25)
    if isinstance(boost, bool) or not isinstance(boost, (int, float)) or not 0 <= boost <= 1:
        raise ManifestError("scoring.dependency_boost must be a number from 0 to 1")
    scoring["dependency_boost"] = float(boost)

    raw_items = root.get("items")
    if not isinstance(raw_items, list):
        raise ManifestError("items must be an array")

    by_id: dict[str, dict[str, Any]] = {}
    for index, raw_item in enumerate(raw_items):
        backlog_item = _require_mapping(raw_item, f"items[{index}]")
        _reject_unknown(backlog_item, ITEM_FIELDS, f"items[{index}]")
        item_id = _require_nonempty_string(backlog_item.get("id"), f"items[{index}].id")
        if not ID_PATTERN.fullmatch(item_id):
            raise ManifestError(
                f"Item id '{item_id}' must use 1-64 letters, digits, dots, underscores, or hyphens"
            )
        if item_id in by_id:
            raise ManifestError(f"Duplicate item id '{item_id}'")
        backlog_item["id"] = item_id
        backlog_item["title"] = _require_nonempty_string(
            backlog_item.get("title"), f"Item '{item_id}' title"
        )
        backlog_item["description"] = _require_nonempty_string(
            backlog_item.get("description"), f"Item '{item_id}' description"
        )
        item_type = _require_nonempty_string(
            backlog_item.get("type"), f"Item '{item_id}' type"
        )
        if item_type not in levels:
            raise ManifestError(
                f"Item '{item_id}' type '{item_type}' is not in workflow.hierarchy"
            )
        backlog_item["type"] = item_type

        for dimension, minimum in (
            ("impact", 1),
            ("effort", 1),
            ("business_value", 1),
            ("enabler_value", 0),
        ):
            _validate_dimension(backlog_item, dimension, minimum)

        status = backlog_item.get("status")
        if status not in statuses:
            raise ManifestError(f"Item '{item_id}' has unknown status '{status}'")
        maturity = backlog_item.setdefault("maturity", "ready")
        if maturity not in {"idea", "refined", "ready"}:
            raise ManifestError(
                f"Item '{item_id}' maturity must be idea, refined, or ready"
            )
        criteria = backlog_item.get("acceptance_criteria")
        if not isinstance(criteria, list) or any(
            not isinstance(criterion, str) or not criterion.strip()
            for criterion in criteria
        ):
            raise ManifestError(
                f"Item '{item_id}' acceptance_criteria must be an array of non-empty strings"
            )
        if maturity == "ready" and not criteria:
            raise ManifestError(
                f"Item '{item_id}' must have acceptance criteria before maturity is ready"
            )

        dependencies = backlog_item.setdefault("depends_on", [])
        if not isinstance(dependencies, list) or any(
            not isinstance(value, str) or not value for value in dependencies
        ):
            raise ManifestError(f"Item '{item_id}' depends_on must be an array of item ids")
        if len(dependencies) != len(set(dependencies)):
            raise ManifestError(f"Item '{item_id}' depends_on contains duplicates")
        if item_id in dependencies:
            raise ManifestError(f"Item '{item_id}' cannot depend on itself")
        parent = backlog_item.setdefault("parent", None)
        if parent is not None and (not isinstance(parent, str) or not parent):
            raise ManifestError(f"Item '{item_id}' parent must be an item id or null")
        sprint = backlog_item.setdefault("sprint", None)
        if sprint is not None and (not isinstance(sprint, str) or not sprint.strip()):
            raise ManifestError(f"Item '{item_id}' sprint must be a non-empty string or null")
        if isinstance(sprint, str):
            backlog_item["sprint"] = sprint.strip()
        by_id[item_id] = backlog_item

    for item_id, backlog_item in by_id.items():
        parent_id = backlog_item["parent"]
        if parent_id is not None:
            if parent_id not in by_id:
                raise ManifestError(f"Item '{item_id}' references unknown parent '{parent_id}'")
            parent_type = by_id[parent_id]["type"]
            if levels[backlog_item["type"]] != levels[parent_type] + 1:
                raise ManifestError(
                    f"Item '{item_id}' type '{backlog_item['type']}' must be a direct child "
                    f"of parent '{parent_id}' type '{parent_type}'"
                )
        for dependency in backlog_item["depends_on"]:
            if dependency not in by_id:
                raise ManifestError(
                    f"Item '{item_id}' references unknown dependency '{dependency}'"
                )

    cycle = _find_dependency_cycle(by_id)
    if cycle:
        raise ManifestError(f"Dependency cycle detected: {' -> '.join(cycle)}")

    root["items"] = [by_id[item_id] for item_id in sorted(by_id)]
    return root


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"Manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(
            f"Manifest is invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    return validate_manifest(data)


def default_manifest(owner: str, repository: str, project_number: int) -> dict[str, Any]:
    """Create the smallest tracked manifest; remote operational state stays on GitHub."""

    return validate_manifest(
        {
            "schema_version": SCHEMA_VERSION,
            "github": {
                "owner": owner,
                "repository": repository,
                "project_number": project_number,
                "issue_type_mode": "native_or_label",
            },
            "workflow": {
                "statuses": list(DEFAULT_STATUSES),
                "done_statuses": ["Done"],
                "work_item_types": list(DEFAULT_WORK_ITEM_TYPES),
                "default_capacity": 20,
                "iteration": {
                    "field": "Sprint",
                    "start_date": date.today().isoformat(),
                    "duration_days": 14,
                },
            },
            "scoring": {
                "weights": deepcopy(DEFAULT_WEIGHTS),
                "dependency_boost": 0.25,
            },
            "items": [],
        }
    )
