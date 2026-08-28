from __future__ import annotations

from copy import deepcopy


def item(
    item_id: str,
    *,
    title: str | None = None,
    item_type: str = "Task",
    parent: str | None = None,
    depends_on: list[str] | None = None,
    impact: int = 3,
    effort: int = 3,
    business_value: int = 3,
    enabler_value: int = 0,
    status: str = "Ready",
    maturity: str = "ready",
    sprint: str | None = None,
) -> dict:
    return {
        "id": item_id,
        "title": title or item_id,
        "type": item_type,
        "description": f"Outcome for {item_id}",
        "acceptance_criteria": [f"{item_id} is verifiably complete"],
        "parent": parent,
        "depends_on": depends_on or [],
        "impact": impact,
        "effort": effort,
        "business_value": business_value,
        "enabler_value": enabler_value,
        "status": status,
        "maturity": maturity,
        "sprint": sprint,
    }


def manifest(*items: dict) -> dict:
    return {
        "schema_version": 1,
        "github": {
            "owner": "aegolius-labs",
            "repository": "example",
            "project_number": 1,
            "issue_type_mode": "native_or_label",
        },
        "workflow": {
            "statuses": [
                "Inbox",
                "Refining",
                "Ready",
                "Planned",
                "In Progress",
                "In Review",
                "Done",
                "Blocked",
            ],
            "done_statuses": ["Done"],
            "work_item_types": ["Story", "Bug", "Task"],
            "default_capacity": 10,
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
        "items": deepcopy(list(items)),
    }

