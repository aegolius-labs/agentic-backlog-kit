from __future__ import annotations

from typing import Any

from .github import GitHubApiError, GitHubTransport
from .sync import extract_item_id


def _scaffold_fields(project: dict[str, Any]) -> list[dict[str, Any]]:
    fields = []
    for field in (project.get("fields") or {}).get("nodes") or []:
        if not field.get("name") or not field.get("dataType"):
            continue
        fields.append(
            {
                "name": field["name"],
                "data_type": field["dataType"],
                "options": field.get("options", []),
                "id": field.get("id"),
                "database_id": field.get("databaseId"),
            }
        )
    return sorted(fields, key=lambda field: str(field["name"]))


def _scaffold_views(project: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted([
        {"name": view.get("name"), "layout": str(view.get("layout", "")).lower()}
        for view in (project.get("views") or {}).get("nodes") or []
        if view.get("name")
    ], key=lambda view: str(view["name"]))


class GitHubSnapshotReader:
    """Read only the managed GitHub state needed for deterministic reconciliation."""

    def __init__(
        self,
        transport: GitHubTransport,
        *,
        owner: str,
        repository: str,
        project_number: int,
    ) -> None:
        self.transport = transport
        self.owner = owner
        self.repository = repository
        self.project_number = project_number

    @property
    def repository_path(self) -> str:
        return f"/repos/{self.owner}/{self.repository}"

    def _list_issues(self) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self.transport.rest(
                "GET",
                f"{self.repository_path}/issues?state=all&per_page=100&page={page}",
            )
            if not isinstance(batch, list):
                raise GitHubApiError(200, "List issues response was not an array")
            issues.extend(issue for issue in batch if "pull_request" not in issue)
            if len(batch) < 100:
                return issues
            page += 1

    def _project_items(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        cursor: str | None = None
        while True:
            data = self.transport.graphql(
                """
                query ProjectItems($owner: String!, $number: Int!, $cursor: String) {
                  organization(login: $owner) {
                    projectV2(number: $number) {
                      items(first: 100, after: $cursor) {
                        nodes {
                          id
                          content {
                            ... on Issue {
                              id number
                              repository { nameWithOwner }
                            }
                          }
                          fieldValues(first: 100) {
                            nodes {
                              ... on ProjectV2ItemFieldTextValue {
                                field { ... on ProjectV2Field { name } }
                                text
                              }
                              ... on ProjectV2ItemFieldNumberValue {
                                field { ... on ProjectV2Field { name } }
                                number
                              }
                              ... on ProjectV2ItemFieldSingleSelectValue {
                                field { ... on ProjectV2SingleSelectField { name } }
                                name
                              }
                              ... on ProjectV2ItemFieldIterationValue {
                                field { ... on ProjectV2IterationField { name } }
                                title
                              }
                              ... on ProjectV2ItemFieldDateValue {
                                field { ... on ProjectV2Field { name } }
                                date
                              }
                            }
                          }
                        }
                        pageInfo { hasNextPage endCursor }
                      }
                    }
                  }
                }
                """,
                {
                    "owner": self.owner,
                    "number": self.project_number,
                    "cursor": cursor,
                },
            )
            project = (data.get("organization") or {}).get("projectV2")
            if not project:
                raise GitHubApiError(
                    404,
                    f"Organization project {self.owner}#{self.project_number} was not found",
                )
            connection = project.get("items") or {}
            for project_item in connection.get("nodes") or []:
                content = project_item.get("content") or {}
                repository = (content.get("repository") or {}).get("nameWithOwner")
                if repository and repository.casefold() != f"{self.owner}/{self.repository}".casefold():
                    continue
                node_id = content.get("id")
                if not node_id:
                    continue
                fields: dict[str, Any] = {}
                for field_value in (project_item.get("fieldValues") or {}).get("nodes") or []:
                    field_name = (field_value.get("field") or {}).get("name")
                    if not field_name:
                        continue
                    for key in ("text", "number", "name", "title", "date"):
                        if field_value.get(key) is not None:
                            fields[field_name] = field_value[key]
                            break
                result[str(node_id)] = {
                    "project_item_id": project_item.get("id"),
                    "project_fields": fields,
                }
            page_info = connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                return result
            cursor = page_info.get("endCursor")

    @staticmethod
    def _item_id_from_issue(issue: dict[str, Any] | None) -> str | None:
        return extract_item_id((issue or {}).get("body"))

    @staticmethod
    def _label_names(issue: dict[str, Any]) -> list[str]:
        names = []
        for label in issue.get("labels") or []:
            name = label.get("name") if isinstance(label, dict) else label
            if isinstance(name, str) and name:
                names.append(name)
        return sorted(set(names))

    @staticmethod
    def _fallback_issue_type(labels: list[str]) -> str | None:
        known = {
            "initiative": "Initiative",
            "epic": "Epic",
            "feature": "Feature",
            "story": "Story",
            "bug": "Bug",
            "task": "Task",
        }
        for label in labels:
            prefix, separator, value = label.partition(":")
            if separator and prefix.casefold() == "type":
                matched = known.get(value.casefold())
                if matched:
                    return matched
        return None

    def read(self) -> dict[str, Any]:
        all_issues = self._list_issues()
        managed = [
            issue for issue in all_issues if self._item_id_from_issue(issue) is not None
        ]
        project_items = self._project_items()
        snapshot_issues: list[dict[str, Any]] = []

        for issue in sorted(managed, key=lambda value: int(value["number"])):
            number = int(issue["number"])
            try:
                parent = self.transport.rest(
                    "GET", f"{self.repository_path}/issues/{number}/parent"
                )
            except GitHubApiError as exc:
                if exc.status != 404:
                    raise
                parent = None
            dependencies = self.transport.rest(
                "GET",
                f"{self.repository_path}/issues/{number}/dependencies/blocked_by?per_page=100",
            )
            project_state = project_items.get(str(issue["node_id"]), {})
            raw_type = issue.get("type")
            issue_type = raw_type.get("name") if isinstance(raw_type, dict) else raw_type
            labels = self._label_names(issue)
            if not issue_type:
                issue_type = self._fallback_issue_type(labels)
            snapshot_issues.append(
                {
                    "abk_id": self._item_id_from_issue(issue),
                    "number": number,
                    "id": int(issue["id"]),
                    "node_id": str(issue["node_id"]),
                    "url": str(issue.get("html_url") or issue.get("url") or ""),
                    "title": issue.get("title", ""),
                    "body": issue.get("body") or "",
                    "type": issue_type,
                    "labels": labels,
                    "state": issue.get("state"),
                    "in_project": bool(project_state),
                    "project_item_id": project_state.get("project_item_id"),
                    "project_fields": project_state.get("project_fields", {}),
                    "parent_abk_id": self._item_id_from_issue(parent),
                    "depends_on_abk_ids": sorted(
                        item_id
                        for item_id in (
                            self._item_id_from_issue(dependency)
                            for dependency in dependencies
                        )
                        if item_id
                    ),
                }
            )
        return {
            "schema_version": 1,
            "github": {
                "owner": self.owner,
                "repository": self.repository,
                "project_number": self.project_number,
            },
            "issues": snapshot_issues,
        }


class GitHubProjectDiscoveryReader:
    """Discover organization Projects and the repository links needed for bootstrap."""

    def __init__(
        self, transport: GitHubTransport, *, owner: str, repository: str
    ) -> None:
        self.transport = transport
        self.owner = owner
        self.repository = repository

    def _labels(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self.transport.rest(
                "GET",
                f"/repos/{self.owner}/{self.repository}/labels?per_page=100&page={page}",
            )
            if not isinstance(batch, list):
                raise GitHubApiError(200, "List labels response was not an array")
            result.extend(batch)
            if len(batch) < 100:
                return result
            page += 1

    @staticmethod
    def _project_fragment() -> str:
        return """
          nodes {
            id number title url closed
            fields(first: 100) {
              nodes {
                __typename
                ... on ProjectV2Field { id databaseId name dataType }
                ... on ProjectV2SingleSelectField {
                  id databaseId name dataType
                  options { id name color description }
                }
                ... on ProjectV2IterationField {
                  id databaseId name dataType
                  configuration { duration startDay }
                }
              }
            }
            views(first: 100) { nodes { name layout } }
          }
          pageInfo { hasNextPage endCursor }
        """

    def read(self) -> dict[str, Any]:
        data = self.transport.graphql(
            f"""
            query DiscoverProjects($owner: String!, $repository: String!) {{
              organization(login: $owner) {{
                id
                projectsV2(first: 100, orderBy: {{field: NUMBER, direction: ASC}}) {{
                  {self._project_fragment()}
                }}
              }}
              repository(owner: $owner, name: $repository) {{
                id name
                projectsV2(first: 100) {{
                  nodes {{ id }}
                  pageInfo {{ hasNextPage endCursor }}
                }}
              }}
            }}
            """,
            {"owner": self.owner, "repository": self.repository},
        )
        organization = data.get("organization")
        repository = data.get("repository")
        if not isinstance(organization, dict):
            raise GitHubApiError(404, f"Organization '{self.owner}' was not found")
        if not isinstance(repository, dict):
            raise GitHubApiError(
                404, f"Repository '{self.owner}/{self.repository}' was not found"
            )

        project_connection = organization.get("projectsV2") or {}
        raw_projects = list(project_connection.get("nodes") or [])
        cursor = (project_connection.get("pageInfo") or {}).get("endCursor")
        while (project_connection.get("pageInfo") or {}).get("hasNextPage"):
            page = self.transport.graphql(
                f"""
                query MoreProjects($owner: String!, $cursor: String!) {{
                  organization(login: $owner) {{
                    projectsV2(first: 100, after: $cursor,
                      orderBy: {{field: NUMBER, direction: ASC}}) {{
                      {self._project_fragment()}
                    }}
                  }}
                }}
                """,
                {"owner": self.owner, "cursor": cursor},
            )
            project_connection = (
                (page.get("organization") or {}).get("projectsV2") or {}
            )
            raw_projects.extend(project_connection.get("nodes") or [])
            cursor = (project_connection.get("pageInfo") or {}).get("endCursor")

        linked_connection = repository.get("projectsV2") or {}
        linked_ids = {
            str(node["id"])
            for node in linked_connection.get("nodes") or []
            if node.get("id")
        }
        cursor = (linked_connection.get("pageInfo") or {}).get("endCursor")
        while (linked_connection.get("pageInfo") or {}).get("hasNextPage"):
            page = self.transport.graphql(
                """
                query MoreLinkedProjects($owner: String!, $repository: String!, $cursor: String!) {
                  repository(owner: $owner, name: $repository) {
                    projectsV2(first: 100, after: $cursor) {
                      nodes { id }
                      pageInfo { hasNextPage endCursor }
                    }
                  }
                }
                """,
                {
                    "owner": self.owner,
                    "repository": self.repository,
                    "cursor": cursor,
                },
            )
            linked_connection = (page.get("repository") or {}).get("projectsV2") or {}
            linked_ids.update(
                str(node["id"])
                for node in linked_connection.get("nodes") or []
                if node.get("id")
            )
            cursor = (linked_connection.get("pageInfo") or {}).get("endCursor")

        projects = [
            {
                "id": str(project.get("id") or ""),
                "number": project.get("number"),
                "title": project.get("title"),
                "url": project.get("url"),
                "closed": bool(project.get("closed")),
                "linked": str(project.get("id")) in linked_ids,
                "fields": _scaffold_fields(project),
                "views": _scaffold_views(project),
            }
            for project in raw_projects
        ]
        try:
            projects.sort(key=lambda project: int(project["number"]))
        except (TypeError, ValueError) as exc:
            raise GitHubApiError(
                200, "Project discovery returned invalid identity"
            ) from exc
        return {
            "organization": {"login": self.owner, "id": organization.get("id")},
            "repository": {"name": self.repository, "id": repository.get("id")},
            "projects": projects,
            "labels": self._labels(),
        }


class GitHubScaffoldSnapshotReader:
    """Read Project shape and repository labels for an idempotent scaffold plan."""

    def __init__(
        self,
        transport: GitHubTransport,
        *,
        owner: str,
        repository: str,
        project_number: int,
    ) -> None:
        self.transport = transport
        self.owner = owner
        self.repository = repository
        self.project_number = project_number

    def _labels(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self.transport.rest(
                "GET",
                f"/repos/{self.owner}/{self.repository}/labels?per_page=100&page={page}",
            )
            if not isinstance(batch, list):
                raise GitHubApiError(200, "List labels response was not an array")
            result.extend(batch)
            if len(batch) < 100:
                return sorted(result, key=lambda label: str(label.get("name", "")))
            page += 1

    def read(self) -> dict[str, Any]:
        data = self.transport.graphql(
            """
            query ProjectScaffold($owner: String!, $number: Int!) {
              organization(login: $owner) {
                projectV2(number: $number) {
                  fields(first: 100) {
                    nodes {
                      __typename
                      ... on ProjectV2Field { id databaseId name dataType }
                      ... on ProjectV2SingleSelectField {
                        id databaseId name dataType
                        options { id name color description }
                      }
                      ... on ProjectV2IterationField {
                        id databaseId name dataType
                        configuration { duration startDay }
                      }
                    }
                  }
                  views(first: 100) {
                    nodes { name layout }
                  }
                }
              }
            }
            """,
            {"owner": self.owner, "number": self.project_number},
        )
        project = (data.get("organization") or {}).get("projectV2")
        if not project:
            raise GitHubApiError(
                404,
                f"Organization project {self.owner}#{self.project_number} was not found",
            )
        return {
            "fields": _scaffold_fields(project),
            "views": _scaffold_views(project),
            "labels": self._labels(),
        }
