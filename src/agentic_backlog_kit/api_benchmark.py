"""Deterministic GitHub API-call counts for snapshot, plan and apply.

Byte budgets protect what a command prints; they say nothing about how many
requests it costs to produce.  GitHub rate-limits by request, so a change that
quietly adds a call per issue is invisible to the byte benchmark yet caps the
backlog size a repository can sync in an hour.

This module drives the real snapshot reader, sync planner and plan executor
against an in-memory repository that answers the exact REST and GraphQL
shapes they send, and counts every transport call per phase.  Nothing here
contacts GitHub, and the counts are a pure function of the fixture, so the
same commit produces the same numbers everywhere.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlsplit

from .capabilities import require_capabilities
from .github import GitHubPlanExecutor, GitHubService
from .snapshot import GitHubSnapshotReader
from .sync import apply_plan, build_sync_plan


API_CALL_SIZES = (100, 1_000, 5_000)
API_CALL_PHASES = ("snapshot", "plan", "apply", "cold-apply")

# Budgets are a fixed allowance plus an allowance per 1,000 issues.  Reads are
# paged, so their slope is a few dozen calls per 1,000 issues; a regression to
# one request per issue adds 1,000 and fails loudly.  A cold apply writes every
# item and cannot be paged, so its slope is several calls per issue and its
# headroom is kept below one extra call per issue to catch exactly that kind
# of regression.
API_CALL_BUDGETS: dict[str, dict[str, int]] = {
    # One listing page per 100 issues, one Project page per 100 items and one
    # relationship query per 50 issues: 40 calls per 1,000 issues.
    "snapshot": {"base_calls": 4, "per_1000_issues": 50},
    # Planning is pure: it reads the snapshot it is given and calls nothing.
    "plan": {"base_calls": 0, "per_1000_issues": 0},
    # Re-applying a converged backlog costs only the refresh before apply.
    "apply": {"base_calls": 4, "per_1000_issues": 50},
    # Create, add to the Project, then one write per Project field; plus the
    # dependency writes the fixture's fan-out needs.
    "cold-apply": {"base_calls": 8, "per_1000_issues": 8_600},
}

_ALIAS = re.compile(r"\bi(\d+): issue\(number: (\d+)\)")
_ISSUE_PATH = re.compile(r"^/repos/[^/]+/[^/]+/issues/(\d+)(/.*)?$")


def api_call_budget(phase: str, issue_count: int) -> int:
    """Return the maximum number of transport calls one phase may make."""

    try:
        spec = API_CALL_BUDGETS[phase]
    except KeyError as exc:
        raise ValueError(f"Unknown API-call phase: {phase}") from exc
    return spec["base_calls"] + math.ceil(spec["per_1000_issues"] * issue_count / 1000)


class SimulatedGitHub:
    """An in-memory repository and organization Project that counts calls.

    It answers only the requests the reader, planner and executor actually
    send and fails on anything else, so a new kind of call cannot slip past
    the count by being silently ignored.
    """

    route = "simulated"

    def __init__(self, manifest: Mapping[str, Any]) -> None:
        github = manifest["github"]
        self.owner = github["owner"]
        self.repository = github["repository"]
        self.issues: list[dict[str, Any]] = []
        self.parents: dict[int, int] = {}
        self.blocked_by: dict[int, list[int]] = {}
        self.project_items: list[dict[str, Any]] = []
        self.fields = self._fields(manifest)
        self.rest_calls = 0
        self.graphql_calls = 0

    @staticmethod
    def _fields(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
        workflow = manifest["workflow"]
        fields: list[dict[str, Any]] = [
            {
                "id": "FIELD_STATUS",
                "name": "Status",
                "dataType": "SINGLE_SELECT",
                "options": [
                    {"id": f"OPT_{index}", "name": name}
                    for index, name in enumerate(workflow["statuses"])
                ],
            }
        ]
        for name in ("Impact", "Effort", "Business Value", "Enabler Value", "Priority"):
            fields.append(
                {
                    "id": f"FIELD_{name.upper().replace(' ', '_')}",
                    "name": name,
                    "dataType": "NUMBER",
                }
            )
        iteration = workflow.get("iteration") or {}
        titles = sorted(
            {item["sprint"] for item in manifest["items"] if item.get("sprint")}
        )
        fields.append(
            {
                "id": "FIELD_SPRINT",
                "name": iteration.get("field", "Sprint"),
                "dataType": "ITERATION",
                "configuration": {
                    "iterations": [
                        {"id": f"ITER_{index}", "title": title}
                        for index, title in enumerate(titles)
                    ],
                    "completedIterations": [],
                },
            }
        )
        return fields

    def reset_counts(self) -> None:
        self.rest_calls = 0
        self.graphql_calls = 0

    def counts(self) -> dict[str, int]:
        return {
            "rest": self.rest_calls,
            "graphql": self.graphql_calls,
            "total": self.rest_calls + self.graphql_calls,
        }

    # -- REST -------------------------------------------------------------

    def _issue(self, number: int) -> dict[str, Any]:
        return self.issues[number - 1]

    def _number_for_database_id(self, database_id: int) -> int:
        return int(database_id) - 100_000

    def rest(self, method: str, path: str, payload: Any = None) -> Any:
        self.rest_calls += 1
        prefix = f"/repos/{self.owner}/{self.repository}/issues"
        if method == "GET" and path.startswith(prefix + "?"):
            query = parse_qs(urlsplit(path).query)
            page = int(query["page"][0])
            per_page = int(query["per_page"][0])
            start = (page - 1) * per_page
            return [dict(issue) for issue in self.issues[start : start + per_page]]
        if method == "POST" and path == prefix:
            number = len(self.issues) + 1
            issue = {
                "id": 100_000 + number,
                "node_id": f"ISSUE_{number}",
                "number": number,
                "html_url": f"https://github.com/{self.owner}/{self.repository}/issues/{number}",
                "title": payload["title"],
                "body": payload.get("body", ""),
                "state": "open",
                "type": {"name": payload["type"]} if payload.get("type") else None,
                "labels": [{"name": name} for name in payload.get("labels", [])],
            }
            self.issues.append(issue)
            return dict(issue)
        match = _ISSUE_PATH.match(path)
        if match:
            number = int(match.group(1))
            suffix = match.group(2) or ""
            if method == "PATCH" and not suffix:
                issue = self._issue(number)
                for key in ("title", "body", "state"):
                    if key in payload:
                        issue[key] = payload[key]
                if "type" in payload:
                    issue["type"] = {"name": payload["type"]}
                if "labels" in payload:
                    issue["labels"] = [{"name": name} for name in payload["labels"]]
                return dict(issue)
            if method == "POST" and suffix == "/labels":
                issue = self._issue(number)
                issue["labels"] = [{"name": name} for name in payload["labels"]]
                return issue["labels"]
            if method == "POST" and suffix == "/sub_issues":
                child = self._number_for_database_id(payload["sub_issue_id"])
                self.parents[child] = number
                return {}
            if method == "POST" and suffix == "/dependencies/blocked_by":
                blocker = self._number_for_database_id(payload["issue_id"])
                self.blocked_by.setdefault(number, []).append(blocker)
                return {}
        raise AssertionError(f"Simulated GitHub has no answer for {method} {path}")

    # -- GraphQL ----------------------------------------------------------

    def _related(self, number: int) -> dict[str, Any]:
        issue = self._issue(number)
        return {
            "number": number,
            "body": issue["body"],
            "repository": {"nameWithOwner": f"{self.owner}/{self.repository}"},
        }

    def _field_value(self, field: dict[str, Any], value: Any) -> dict[str, Any]:
        node: dict[str, Any] = {"field": {"name": field["name"]}}
        if field["dataType"] == "NUMBER":
            node["number"] = value
        elif field["dataType"] == "SINGLE_SELECT":
            node["name"] = value
        elif field["dataType"] == "ITERATION":
            node["title"] = value
        else:
            node["text"] = value
        return node

    def _page(self, cursor: str | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        start = int(cursor) if cursor else 0
        end = start + 100
        more = end < len(self.project_items)
        return self.project_items[start:end], {
            "hasNextPage": more,
            "endCursor": str(end) if more else None,
        }

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        self.graphql_calls += 1
        if "query Relationships" in query:
            repository: dict[str, Any] = {}
            for alias, number_text in _ALIAS.findall(query):
                number = int(number_text)
                parent = self.parents.get(number)
                blockers = self.blocked_by.get(number, [])
                if len(blockers) > 100:
                    raise AssertionError("Simulated GitHub does not page blockedBy")
                repository[f"i{alias}"] = {
                    "parent": self._related(parent) if parent else None,
                    "blockedBy": {
                        "nodes": [self._related(blocker) for blocker in blockers],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                }
            return {"repository": repository}
        if "query ProjectItems($owner" in query:
            items, page_info = self._page(variables.get("cursor"))
            by_name = {field["name"]: field for field in self.fields}
            nodes = [
                {
                    "id": item["id"],
                    "content": {
                        "id": item["content"],
                        "number": item["number"],
                        "repository": {
                            "nameWithOwner": f"{self.owner}/{self.repository}"
                        },
                    },
                    "fieldValues": {
                        "nodes": [
                            self._field_value(by_name[name], value)
                            for name, value in sorted(item["fields"].items())
                        ]
                    },
                }
                for item in items
            ]
            return {
                "organization": {
                    "projectV2": {"items": {"nodes": nodes, "pageInfo": page_info}}
                }
            }
        if "query ProjectItems($project" in query:
            items, page_info = self._page(variables.get("cursor"))
            nodes = [{"id": item["id"], "content": {"id": item["content"]}} for item in items]
            return {"node": {"items": {"nodes": nodes, "pageInfo": page_info}}}
        if "query Project(" in query:
            return {
                "organization": {
                    "projectV2": {"id": "PROJECT_1", "fields": {"nodes": self.fields}}
                }
            }
        if "mutation AddItem" in query:
            content = variables["content"]
            number = int(content.split("_")[1])
            item_id = f"ITEM_{len(self.project_items) + 1}"
            self.project_items.append(
                {"id": item_id, "content": content, "number": number, "fields": {}}
            )
            return {"addProjectV2ItemById": {"item": {"id": item_id}}}
        if "mutation SetField" in query:
            item = next(
                candidate
                for candidate in self.project_items
                if candidate["id"] == variables["item"]
            )
            field = next(
                candidate for candidate in self.fields if candidate["id"] == variables["field"]
            )
            value = variables["value"]
            if "number" in value:
                stored: Any = value["number"]
            elif "text" in value:
                stored = value["text"]
            elif "singleSelectOptionId" in value:
                stored = next(
                    option["name"]
                    for option in field["options"]
                    if option["id"] == value["singleSelectOptionId"]
                )
            else:
                stored = next(
                    iteration["title"]
                    for iteration in field["configuration"]["iterations"]
                    if iteration["id"] == value["iterationId"]
                )
            item["fields"][field["name"]] = stored
            return {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": item["id"]}}}
        raise AssertionError("Simulated GitHub has no answer for this GraphQL query")


def _reader(transport: SimulatedGitHub, manifest: Mapping[str, Any]) -> GitHubSnapshotReader:
    github = manifest["github"]
    return GitHubSnapshotReader(
        transport,
        owner=github["owner"],
        repository=github["repository"],
        project_number=github["project_number"],
    )


def _apply(transport: SimulatedGitHub, manifest: dict[str, Any], plan: Any) -> None:
    """Run the same refresh, capability check and apply that ``sync-apply`` runs."""

    github = manifest["github"]
    snapshot = _reader(transport, manifest).read()
    service = GitHubService(
        transport,
        owner=github["owner"],
        repository=github["repository"],
        project_number=github["project_number"],
        issue_type_mode=github["issue_type_mode"],
    )
    require_capabilities(transport, [action.kind for action in plan.actions])
    apply_plan(
        plan,
        executor=GitHubPlanExecutor(service, remote_snapshot=snapshot),
        confirmation=plan.digest,
        manifest=manifest,
        remote_snapshot=snapshot,
    )


def measure_api_calls(manifest: dict[str, Any]) -> dict[str, Any]:
    """Count transport calls for each phase of a cold and a converged sync."""

    issue_count = len(manifest["items"])
    transport = SimulatedGitHub(manifest)

    # Cold: an empty repository, so every item is created and written.
    empty = _reader(transport, manifest).read()
    cold_plan = build_sync_plan(manifest, empty)
    transport.reset_counts()
    _apply(transport, manifest, cold_plan)
    cold_apply = transport.counts()

    # Converged: the repository the cold apply produced.
    transport.reset_counts()
    snapshot = _reader(transport, manifest).read()
    snapshot_calls = transport.counts()
    transport.reset_counts()
    plan = build_sync_plan(manifest, snapshot)
    plan_calls = transport.counts()
    if plan.actions:
        kinds = sorted({action.kind for action in plan.actions})
        raise AssertionError(
            "The simulated repository did not converge after a cold apply; "
            f"{len(plan.actions)} actions remain: {', '.join(kinds)}"
        )
    transport.reset_counts()
    _apply(transport, manifest, plan)
    apply_calls = transport.counts()

    return {
        "issues": issue_count,
        "cold_actions": len(cold_plan.actions),
        "phases": {
            "snapshot": snapshot_calls,
            "plan": plan_calls,
            "apply": apply_calls,
            "cold-apply": cold_apply,
        },
    }


def assert_api_call_budgets(runs: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return human-readable failures for any phase over its call budget."""

    failures: list[str] = []
    for run in runs:
        issue_count = run.get("issues")
        phases = run.get("phases")
        if not isinstance(issue_count, int) or not isinstance(phases, Mapping):
            failures.append("malformed API-call run")
            continue
        for phase in API_CALL_PHASES:
            counts = phases.get(phase)
            total = counts.get("total") if isinstance(counts, Mapping) else None
            if not isinstance(total, int):
                failures.append(f"{issue_count} issues {phase}: missing call count")
                continue
            limit = api_call_budget(phase, issue_count)
            if total > limit:
                failures.append(
                    f"{issue_count} issues {phase}: {total} API calls exceeds {limit}"
                )
    return failures


__all__ = [
    "API_CALL_BUDGETS",
    "API_CALL_PHASES",
    "API_CALL_SIZES",
    "SimulatedGitHub",
    "api_call_budget",
    "assert_api_call_budgets",
    "measure_api_calls",
]
