from __future__ import annotations

from typing import Any, Iterable

from .manifest import ManifestError


VIEW_CONFIGURATION_KEYS = (
    "visible_fields",
    "group_by",
    "vertical_group_by",
    "sort_by",
)


def normalize_layout(value: Any) -> str:
    layout = str(value or "").strip().lower()
    if layout.endswith("_layout"):
        layout = layout[: -len("_layout")]
    if layout not in {"table", "board", "roadmap"}:
        raise ManifestError(f"Project view returned unsupported layout '{value}'")
    return layout


def normalize_filter(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ManifestError("Project view filter must be a string")
    return " ".join(value.split())


def normalize_field_reference(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ManifestError("Project view field reference must be an object")
    name = raw.get("name")
    node_id = raw.get("id")
    database_id = raw.get("database_id")
    if database_id is None:
        database_id = raw.get("fullDatabaseId")
    if database_id is None:
        database_id = raw.get("databaseId")
    if not isinstance(name, str) or not name.strip():
        raise ManifestError("Project view field reference has no name")
    if not isinstance(node_id, str) or not node_id:
        raise ManifestError(f"Project view field '{name}' has no GraphQL identity")
    try:
        normalized_database_id = int(database_id)
    except (TypeError, ValueError) as exc:
        raise ManifestError(
            f"Project view field '{name}' has no REST database identity"
        ) from exc
    if normalized_database_id < 1:
        raise ManifestError(
            f"Project view field '{name}' has no REST database identity"
        )
    return {
        "id": node_id,
        "database_id": normalized_database_id,
        "name": name.strip(),
    }


def _connection_nodes(
    connection: Any, *, view_name: str, label: str
) -> list[dict[str, Any]]:
    if not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list):
        raise ManifestError(
            f"Project view '{view_name}' snapshot is missing complete {label} configuration"
        )
    page_info = connection.get("pageInfo")
    if isinstance(page_info, dict) and page_info.get("hasNextPage"):
        raise ManifestError(
            f"Project view '{view_name}' {label} configuration was truncated"
        )
    return connection["nodes"]


def _normalize_references(raw: Any, *, view_name: str, label: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ManifestError(
            f"Project view '{view_name}' snapshot is missing complete {label} configuration"
        )
    return [normalize_field_reference(value) for value in raw]


def canonicalize_view(raw: Any) -> dict[str, Any]:
    """Normalize either a GraphQL view node or an already serialized snapshot view."""

    if not isinstance(raw, dict):
        raise ManifestError("Project view snapshot entry must be an object")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ManifestError("Project view snapshot entry has no name")
    name = name.strip()

    view_id = raw.get("id")
    if not isinstance(view_id, str) or not view_id:
        raise ManifestError(f"Project view '{name}' has no GraphQL identity")
    try:
        number = int(raw.get("number"))
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"Project view '{name}' has no numeric identity") from exc

    if all(key in raw for key in VIEW_CONFIGURATION_KEYS):
        visible_fields = _normalize_references(
            raw["visible_fields"], view_name=name, label="visible fields"
        )
        group_by = _normalize_references(
            raw["group_by"], view_name=name, label="horizontal grouping"
        )
        vertical_group_by = _normalize_references(
            raw["vertical_group_by"], view_name=name, label="vertical grouping"
        )
        raw_sort = raw["sort_by"]
        if not isinstance(raw_sort, list):
            raise ManifestError(
                f"Project view '{name}' snapshot is missing complete sorting configuration"
            )
    else:
        configuration = raw.get("configuration")
        if not isinstance(configuration, dict):
            raise ManifestError(
                f"Project view '{name}' snapshot is missing complete visible fields configuration"
            )
        visible_fields = [
            normalize_field_reference(value)
            for value in _connection_nodes(
                configuration.get("visibleFields"),
                view_name=name,
                label="visible fields",
            )
        ]
        group_by = [
            normalize_field_reference(value)
            for value in _connection_nodes(
                raw.get("groupByFields"),
                view_name=name,
                label="horizontal grouping",
            )
        ]
        vertical_group_by = [
            normalize_field_reference(value)
            for value in _connection_nodes(
                raw.get("verticalGroupByFields"),
                view_name=name,
                label="vertical grouping",
            )
        ]
        raw_sort = _connection_nodes(
            raw.get("sortByFields"), view_name=name, label="sorting"
        )

    sort_by: list[dict[str, Any]] = []
    for entry in raw_sort:
        if not isinstance(entry, dict):
            raise ManifestError(f"Project view '{name}' sorting entry is malformed")
        direction = str(entry.get("direction") or "").lower()
        if direction not in {"asc", "desc"}:
            raise ManifestError(
                f"Project view '{name}' sorting direction '{entry.get('direction')}' is unsupported"
            )
        sort_by.append(
            {
                "field": normalize_field_reference(entry.get("field")),
                "direction": direction,
            }
        )

    return {
        "id": view_id,
        "number": number,
        "name": name,
        "layout": normalize_layout(raw.get("layout")),
        "filter": normalize_filter(raw.get("filter")),
        "visible_fields": visible_fields,
        "group_by": group_by,
        "vertical_group_by": vertical_group_by,
        "sort_by": sort_by,
    }


def normalize_project_views(project: dict[str, Any]) -> list[dict[str, Any]]:
    connection = project.get("views") or {}
    nodes = connection.get("nodes") if isinstance(connection, dict) else None
    if not isinstance(nodes, list):
        raise ManifestError("Project views response was not a connection")
    page_info = connection.get("pageInfo")
    if isinstance(page_info, dict) and page_info.get("hasNextPage"):
        raise ManifestError(
            "Project views collection was truncated; complete state is required"
        )
    result = [canonicalize_view(view) for view in nodes]
    return sorted(
        result,
        key=lambda view: (
            str(view["name"]).casefold(),
            str(view["name"]),
            int(view["number"]),
        ),
    )


def expected_view_specs(iteration_field: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "Backlog",
            "layout": "table",
            "filter": "is:issue",
            "visible_fields": [
                "Title",
                "Status",
                iteration_field,
                "Priority",
                "Impact",
                "Effort",
                "Business Value",
                "Enabler Value",
            ],
            "group_by": [],
            "vertical_group_by": [],
            "sort_by": [{"field": "Priority", "direction": "desc"}],
        },
        {
            "name": "Kanban",
            "layout": "board",
            "filter": "is:issue is:open",
            "visible_fields": ["Title", iteration_field, "Priority", "Effort"],
            "group_by": [],
            "vertical_group_by": ["Status"],
            "sort_by": [],
        },
        {
            "name": "Current Sprint",
            "layout": "board",
            "filter": f"{iteration_field}:@current",
            "visible_fields": ["Title", "Priority", "Effort"],
            "group_by": [],
            "vertical_group_by": ["Status"],
            "sort_by": [],
        },
        {
            "name": "Roadmap",
            "layout": "roadmap",
            "filter": "is:issue -status:Done",
            "visible_fields": [],
            "group_by": [],
            "vertical_group_by": [],
            "sort_by": [],
        },
    ]


def _field_map(fields: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in fields:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
            continue
        name = raw["name"]
        if name in result:
            raise ManifestError(
                f"Project has multiple fields named '{name}'; view references are ambiguous"
            )
        result[name] = raw
    return result


def _resolve_reference(
    name: Any, fields: dict[str, dict[str, Any]], *, require_ids: bool
) -> dict[str, Any]:
    if not isinstance(name, str) or not name:
        raise ManifestError("Desired Project view field reference must be a name")
    current = fields.get(name)
    if current is None:
        if require_ids:
            raise ManifestError(
                f"Desired Project view field '{name}' does not exist and cannot be resolved"
            )
        return {"name": name}
    try:
        return normalize_field_reference(current)
    except ManifestError:
        if require_ids:
            raise ManifestError(
                f"Desired Project view field '{name}' has incomplete GitHub identity"
            ) from None
        return {"name": name}


def resolve_view_spec(
    spec: dict[str, Any],
    fields: Iterable[dict[str, Any]],
    *,
    require_ids: bool,
) -> dict[str, Any]:
    by_name = _field_map(fields)
    visible_fields = [
        _resolve_reference(name, by_name, require_ids=require_ids)
        for name in spec["visible_fields"]
    ]
    group_by = [
        _resolve_reference(name, by_name, require_ids=require_ids)
        for name in spec["group_by"]
    ]
    vertical_group_by = [
        _resolve_reference(name, by_name, require_ids=require_ids)
        for name in spec["vertical_group_by"]
    ]
    sort_by = [
        {
            "field": _resolve_reference(
                entry["field"], by_name, require_ids=require_ids
            ),
            "direction": str(entry["direction"]).lower(),
        }
        for entry in spec["sort_by"]
    ]
    return {
        "name": str(spec["name"]),
        "layout": normalize_layout(spec["layout"]),
        "filter": normalize_filter(spec.get("filter")),
        "visible_fields": visible_fields,
        "group_by": group_by,
        "vertical_group_by": vertical_group_by,
        "sort_by": sort_by,
    }


def semantic_view_configuration(view: dict[str, Any]) -> dict[str, Any]:
    """Compare field meaning while keeping API identities in plans and receipts."""

    return {
        "layout": normalize_layout(view.get("layout")),
        "filter": normalize_filter(view.get("filter")),
        "visible_fields": [entry["name"] for entry in view["visible_fields"]],
        "group_by": [entry["name"] for entry in view["group_by"]],
        "vertical_group_by": [
            entry["name"] for entry in view["vertical_group_by"]
        ],
        "sort_by": [
            {"field": entry["field"]["name"], "direction": entry["direction"]}
            for entry in view["sort_by"]
        ],
    }
