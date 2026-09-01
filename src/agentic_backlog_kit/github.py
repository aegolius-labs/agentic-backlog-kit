from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .manifest import ManifestError
from .scaffold import ScaffoldAction
from .sync import SyncAction


API_VERSION = "2026-03-10"


class GitHubApiError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"GitHub API error {status}: {message}")
        self.status = status
        self.message = message


class GitHubTransport(Protocol):
    def rest(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any: ...

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]: ...


class GitHubHttpTransport:
    """Small standard-library transport for environments without GitHub CLI."""

    def __init__(
        self,
        token: str,
        *,
        api_url: str = "https://api.github.com",
        timeout: float = 30.0,
    ) -> None:
        if not token:
            raise ValueError("A GitHub token is required")
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

    def rest(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        body = (
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
            if payload is not None
            else None
        )
        request = Request(
            f"{self.api_url}/{path.lstrip('/')}",
            data=body,
            method=method.upper(),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "agentic-backlog-kit/0.1",
                "X-GitHub-Api-Version": API_VERSION,
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(raw).get("message", raw)
            except json.JSONDecodeError:
                message = raw
            raise GitHubApiError(exc.code, message or exc.reason) from exc
        except URLError as exc:
            raise GitHubApiError(0, str(exc.reason)) from exc

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = self.rest(
            "POST", "/graphql", {"query": query, "variables": variables}
        )
        errors = response.get("errors") if isinstance(response, dict) else None
        if errors:
            message = "; ".join(str(error.get("message", error)) for error in errors)
            raise GitHubApiError(200, f"GraphQL: {message}")
        data = response.get("data") if isinstance(response, dict) else None
        if not isinstance(data, dict):
            raise GitHubApiError(200, "GraphQL response did not contain data")
        return data


class GitHubCliTransport:
    """Use an authenticated `gh` session without exposing its token to this process."""

    def __init__(self, executable: str = "gh") -> None:
        self.executable = executable

    def rest(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        command = [
            self.executable,
            "api",
            "--method",
            method.upper(),
            path.lstrip("/"),
            "--header",
            f"X-GitHub-Api-Version: {API_VERSION}",
        ]
        stdin = None
        if payload is not None:
            command.extend(["--input", "-"])
            stdin = json.dumps(payload, separators=(",", ":"))
        result = subprocess.run(
            command,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise GitHubApiError(result.returncode, result.stderr.strip() or "gh api failed")
        if not result.stdout.strip():
            return {}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubApiError(result.returncode, "gh api returned invalid JSON") from exc

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = self.rest(
            "POST", "graphql", {"query": query, "variables": variables}
        )
        errors = response.get("errors") if isinstance(response, dict) else None
        if errors:
            message = "; ".join(str(error.get("message", error)) for error in errors)
            raise GitHubApiError(200, f"GraphQL: {message}")
        data = response.get("data") if isinstance(response, dict) else None
        if not isinstance(data, dict):
            raise GitHubApiError(200, "GraphQL response did not contain data")
        return data


@dataclass(frozen=True, slots=True)
class GitHubIssueRef:
    item_id: str
    number: int
    database_id: int
    node_id: str
    url: str
    project_item_id: str | None = None


class GitHubService:
    """High-level GitHub mutations used by the reviewed sync-plan executor."""

    def __init__(
        self,
        transport: GitHubTransport,
        *,
        owner: str,
        repository: str,
        project_number: int,
        issue_type_mode: str = "native_or_label",
    ) -> None:
        self.transport = transport
        self.owner = owner
        self.repository = repository
        self.project_number = project_number
        self.issue_type_mode = issue_type_mode
        self._project_id: str | None = None
        self._project_fields: dict[str, dict[str, Any]] | None = None
        self._project_items: dict[str, str] = {}

    @property
    def repository_path(self) -> str:
        return f"/repos/{self.owner}/{self.repository}"

    def use_project(self, identity: dict[str, Any]) -> None:
        """Bind later mutations to an already reviewed Project identity."""

        try:
            number = int(identity["number"])
            project_id = str(identity["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ManifestError("Project identity is incomplete") from exc
        if number < 1 or not project_id:
            raise ManifestError("Project identity is incomplete")
        self.project_number = number
        self._project_id = project_id
        self._project_fields = None
        self._project_items = {}

    def create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.transport.graphql(
            """
            mutation CreateProject($input: CreateProjectV2Input!) {
              createProjectV2(input: $input) {
                projectV2 { id number title url }
              }
            }
            """,
            {
                "input": {
                    "ownerId": payload["owner_id"],
                    "repositoryId": payload["repository_id"],
                    "title": payload["title"],
                }
            },
        )
        project = (data.get("createProjectV2") or {}).get("projectV2")
        if not isinstance(project, dict):
            raise GitHubApiError(200, "Project creation did not return its identity")
        identity = {
            "id": str(project.get("id") or ""),
            "number": project.get("number"),
            "title": str(project.get("title") or ""),
            "url": str(project.get("url") or ""),
        }
        self.use_project(identity)
        return identity

    def link_project_repository(self, payload: dict[str, Any]) -> None:
        self.transport.graphql(
            """
            mutation LinkProjectRepository($input: LinkProjectV2ToRepositoryInput!) {
              linkProjectV2ToRepository(input: $input) { repository { id } }
            }
            """,
            {
                "input": {
                    "projectId": payload["project_id"],
                    "repositoryId": payload["repository_id"],
                }
            },
        )

    @staticmethod
    def _issue_ref(item_id: str, response: dict[str, Any]) -> GitHubIssueRef:
        try:
            return GitHubIssueRef(
                item_id=item_id,
                number=int(response["number"]),
                database_id=int(response["id"]),
                node_id=str(response["node_id"]),
                url=str(response.get("html_url") or response["url"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GitHubApiError(200, "Issue response omitted required identity fields") from exc

    def create_issue(self, item_id: str, payload: dict[str, Any]) -> GitHubIssueRef:
        request_payload = {
            "title": payload["title"],
            "body": payload.get("body", ""),
        }
        if self.issue_type_mode == "labels":
            request_payload["labels"] = [payload["fallback_label"]]
        else:
            request_payload["type"] = payload["type"]
        try:
            response = self.transport.rest(
                "POST", f"{self.repository_path}/issues", request_payload
            )
        except GitHubApiError as exc:
            if self.issue_type_mode != "native_or_label" or exc.status != 422:
                raise
            request_payload.pop("type", None)
            request_payload["labels"] = [payload["fallback_label"]]
            response = self.transport.rest(
                "POST", f"{self.repository_path}/issues", request_payload
            )
        return self._issue_ref(item_id, response)

    def update_issue(self, issue: GitHubIssueRef, payload: dict[str, Any]) -> None:
        request_payload = {
            key: value
            for key, value in payload.items()
            if key in {"title", "body", "state"}
        }
        desired_type = payload.get("type")
        desired_labels = payload.get("labels")
        if desired_type and self.issue_type_mode != "labels":
            request_payload["type"] = desired_type
        if desired_type and self.issue_type_mode == "labels":
            if isinstance(desired_labels, list):
                request_payload["labels"] = desired_labels
            else:
                if request_payload:
                    self.transport.rest(
                        "PATCH",
                        f"{self.repository_path}/issues/{issue.number}",
                        request_payload,
                    )
                self.transport.rest(
                    "POST",
                    f"{self.repository_path}/issues/{issue.number}/labels",
                    {"labels": [payload["fallback_label"]]},
                )
                return
        try:
            if request_payload:
                self.transport.rest(
                    "PATCH",
                    f"{self.repository_path}/issues/{issue.number}",
                    request_payload,
                )
        except GitHubApiError as exc:
            if (
                not desired_type
                or self.issue_type_mode != "native_or_label"
                or exc.status != 422
            ):
                raise
            request_payload.pop("type", None)
            if isinstance(desired_labels, list):
                request_payload["labels"] = desired_labels
                self.transport.rest(
                    "PATCH",
                    f"{self.repository_path}/issues/{issue.number}",
                    request_payload,
                )
            else:
                if request_payload:
                    self.transport.rest(
                        "PATCH",
                        f"{self.repository_path}/issues/{issue.number}",
                        request_payload,
                    )
                self.transport.rest(
                    "POST",
                    f"{self.repository_path}/issues/{issue.number}/labels",
                    {"labels": [payload["fallback_label"]]},
                )

    def set_parent(self, child: GitHubIssueRef, parent: GitHubIssueRef) -> None:
        self.transport.rest(
            "POST",
            f"{self.repository_path}/issues/{parent.number}/sub_issues",
            {"sub_issue_id": child.database_id, "replace_parent": True},
        )

    def add_dependency(
        self, issue: GitHubIssueRef, blocker: GitHubIssueRef
    ) -> None:
        self.transport.rest(
            "POST",
            f"{self.repository_path}/issues/{issue.number}/dependencies/blocked_by",
            {"issue_id": blocker.database_id},
        )

    def create_label(self, payload: dict[str, Any]) -> None:
        self.transport.rest("POST", f"{self.repository_path}/labels", payload)

    def create_project_field(self, payload: dict[str, Any]) -> None:
        project_id, _ = self._load_project()
        input_payload: dict[str, Any] = {
            "projectId": project_id,
            "name": payload["name"],
            "dataType": payload["data_type"],
        }
        if payload["data_type"] == "SINGLE_SELECT":
            palette = ("GRAY", "BLUE", "YELLOW", "ORANGE", "GREEN", "PURPLE", "PINK", "RED")
            input_payload["singleSelectOptions"] = [
                {"name": option, "color": palette[index % len(palette)], "description": ""}
                for index, option in enumerate(payload["options"])
            ]
        elif payload["data_type"] == "ITERATION":
            # GitHub currently ignores an empty iterationConfiguration during
            # field creation.  Leave initialization to the separately
            # reviewed iteration-plan/iteration-apply flow after refresh.
            pass
        self.transport.graphql(
            """
            mutation CreateField($input: CreateProjectV2FieldInput!) {
              createProjectV2Field(input: $input) {
                projectV2Field {
                  ... on ProjectV2Field { id name dataType }
                  ... on ProjectV2SingleSelectField { id name dataType }
                  ... on ProjectV2IterationField { id name dataType }
                }
              }
            }
            """,
            {"input": input_payload},
        )
        self._project_fields = None

    def update_project_field_options(self, payload: dict[str, Any]) -> None:
        options = payload.get("options")
        if not isinstance(options, list) or not options:
            raise GitHubApiError(422, "Single-select field update requires options")
        self.transport.graphql(
            """
            mutation UpdateField($input: UpdateProjectV2FieldInput!) {
              updateProjectV2Field(input: $input) {
                projectV2Field {
                  ... on ProjectV2SingleSelectField { id name dataType }
                }
              }
            }
            """,
            {
                "input": {
                    "fieldId": payload["field_id"],
                    "singleSelectOptions": options,
                }
            },
        )
        self._project_fields = None

    def update_project_field_iterations(self, payload: dict[str, Any]) -> None:
        """Replace an iteration schedule with the complete reviewed configuration.

        GitHub's current ProjectV2Iteration input does not accept existing IDs or
        completion state. The reviewed plan carries those as preconditions; the
        mutation repeats all active title/date/duration definitions and refresh
        verification is responsible for confirming their server-owned IDs.
        """

        configuration = payload.get("iteration_configuration")
        if not isinstance(configuration, dict):
            raise GitHubApiError(422, "Iteration field update requires configuration")
        start_date = configuration.get("start_date")
        duration = configuration.get("duration_days")
        iterations = configuration.get("iterations")
        if (
            not isinstance(start_date, str)
            or isinstance(duration, bool)
            or not isinstance(duration, int)
            or duration < 1
            or not isinstance(iterations, list)
            or not iterations
        ):
            raise GitHubApiError(422, "Iteration field update configuration is incomplete")
        mutation_iterations = []
        for raw in iterations:
            if not isinstance(raw, dict):
                raise GitHubApiError(422, "Iteration field update entry is malformed")
            title = raw.get("title")
            entry_start = raw.get("start_date")
            entry_duration = raw.get("duration_days")
            if (
                not isinstance(title, str)
                or not title
                or not isinstance(entry_start, str)
                or isinstance(entry_duration, bool)
                or not isinstance(entry_duration, int)
                or entry_duration < 1
                or raw.get("completed") is not False
            ):
                raise GitHubApiError(422, "Iteration field update entry is incomplete")
            mutation_iterations.append(
                {
                    "title": title,
                    "startDate": entry_start,
                    "duration": entry_duration,
                }
            )
        self.transport.graphql(
            """
            mutation UpdateIterationField($input: UpdateProjectV2FieldInput!) {
              updateProjectV2Field(input: $input) {
                projectV2Field {
                  ... on ProjectV2IterationField { id name dataType }
                }
              }
            }
            """,
            {
                "input": {
                    "fieldId": payload["field_id"],
                    "iterationConfiguration": {
                        "startDate": start_date,
                        "duration": duration,
                        "iterations": mutation_iterations,
                    },
                }
            },
        )
        self._project_fields = None

    def create_project_view(self, payload: dict[str, Any]) -> None:
        _, fields = self._load_project()
        request_payload: dict[str, Any] = {
            "name": payload["name"],
            "layout": payload["layout"],
            "filter": payload.get("filter", ""),
            "sort_by": [
                [
                    self._resolve_view_field(entry["field"], fields)["database_id"],
                    str(entry["direction"]).lower(),
                ]
                for entry in payload.get("sort_by", [])
            ],
            "group_by": [
                self._resolve_view_field(entry, fields)["database_id"]
                for entry in payload.get("group_by", [])
            ],
            "vertical_group_by": [
                self._resolve_view_field(entry, fields)["database_id"]
                for entry in payload.get("vertical_group_by", [])
            ],
        }
        if payload["layout"] != "roadmap":
            request_payload["visible_fields"] = [
                self._resolve_view_field(entry, fields)["database_id"]
                for entry in payload.get("visible_fields", [])
            ]
        self.transport.rest(
            "POST",
            f"/orgs/{self.owner}/projectsV2/{self.project_number}/views",
            request_payload,
        )

    def update_project_view(self, payload: dict[str, Any]) -> None:
        _, fields = self._load_project()
        layout = str(payload["layout"]).lower()
        input_payload: dict[str, Any] = {
            "viewId": payload["view_id"],
            "name": payload["name"],
            "layout": f"{layout.upper()}_LAYOUT",
            "filter": payload.get("filter", ""),
        }
        if layout != "roadmap":
            input_payload["configuration"] = {
                "visibleFieldIds": [
                    self._resolve_view_field(entry, fields)["id"]
                    for entry in payload.get("visible_fields", [])
                ]
            }
        self.transport.graphql(
            """
            mutation UpdateView($input: UpdateProjectV2ViewInput!) {
              updateProjectV2View(input: $input) {
                projectV2View { id number name layout filter }
              }
            }
            """,
            {"input": input_payload},
        )

    @staticmethod
    def _resolve_view_field(
        reference: dict[str, Any], fields: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        if not isinstance(reference, dict) or not isinstance(reference.get("name"), str):
            raise GitHubApiError(422, "Project view field reference is malformed")
        name = reference["name"]
        field = fields.get(name)
        if not field or not field.get("id"):
            raise GitHubApiError(422, f"Project field '{name}' has no GraphQL id")
        database_id = field.get("databaseId", field.get("fullDatabaseId"))
        try:
            database_id = int(database_id)
        except (TypeError, ValueError) as exc:
            raise GitHubApiError(
                422, f"Project field '{name}' has no REST database id"
            ) from exc
        expected_node_id = reference.get("id")
        expected_database_id = reference.get("database_id")
        if expected_node_id is not None and expected_node_id != field["id"]:
            raise GitHubApiError(
                409, f"Project field '{name}' GraphQL identity changed after review"
            )
        if expected_database_id is not None and int(expected_database_id) != database_id:
            raise GitHubApiError(
                409, f"Project field '{name}' REST identity changed after review"
            )
        return {"id": str(field["id"]), "database_id": database_id, "name": name}

    def add_project_item(self, issue: GitHubIssueRef, fields: dict[str, Any]) -> None:
        project_id, _ = self._load_project()
        data = self.transport.graphql(
            """
            mutation AddItem($project: ID!, $content: ID!) {
              addProjectV2ItemById(input: {projectId: $project, contentId: $content}) {
                item { id }
              }
            }
            """,
            {"project": project_id, "content": issue.node_id},
        )
        try:
            project_item_id = data["addProjectV2ItemById"]["item"]["id"]
        except (KeyError, TypeError) as exc:
            raise GitHubApiError(200, "Project add-item response omitted the item id") from exc
        self._project_items[issue.node_id] = project_item_id
        self._set_project_fields(project_item_id, fields)

    def set_project_fields(
        self, issue: GitHubIssueRef, fields: dict[str, Any]
    ) -> None:
        project_item_id = issue.project_item_id or self._project_items.get(issue.node_id)
        if not project_item_id:
            project_item_id = self._find_project_item(issue.node_id)
        self._set_project_fields(project_item_id, fields)

    def _load_project(self) -> tuple[str, dict[str, dict[str, Any]]]:
        if self._project_id and self._project_fields is not None:
            return self._project_id, self._project_fields
        data = self.transport.graphql(
            """
            query Project($owner: String!, $number: Int!) {
              organization(login: $owner) {
                projectV2(number: $number) {
                  id
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
                        configuration {
                          duration startDay
                          iterations { id title startDate duration }
                          completedIterations { id title startDate duration }
                        }
                      }
                    }
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
        self._project_id = str(project["id"])
        nodes = (project.get("fields") or {}).get("nodes") or []
        self._project_fields = {
            node["name"]: node
            for node in nodes
            if isinstance(node, dict) and node.get("name") and node.get("id")
        }
        return self._project_id, self._project_fields

    def _find_project_item(self, issue_node_id: str) -> str:
        project_id, _ = self._load_project()
        cursor: str | None = None
        while True:
            data = self.transport.graphql(
                """
                query ProjectItems($project: ID!, $cursor: String) {
                  node(id: $project) {
                    ... on ProjectV2 {
                      items(first: 100, after: $cursor) {
                        nodes {
                          id
                          content { ... on Issue { id } }
                        }
                        pageInfo { hasNextPage endCursor }
                      }
                    }
                  }
                }
                """,
                {"project": project_id, "cursor": cursor},
            )
            connection = ((data.get("node") or {}).get("items") or {})
            for node in connection.get("nodes") or []:
                content = node.get("content") or {}
                if content.get("id") == issue_node_id:
                    self._project_items[issue_node_id] = node["id"]
                    return node["id"]
            page_info = connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
        raise GitHubApiError(404, "Issue is not present in the configured Project")

    def _set_project_fields(
        self, project_item_id: str, fields: dict[str, Any]
    ) -> None:
        project_id, metadata = self._load_project()
        for name in sorted(fields):
            if name not in metadata:
                raise GitHubApiError(422, f"Project field '{name}' does not exist")
            field = metadata[name]
            data_type = field.get("dataType")
            raw_value = fields[name]
            if data_type == "NUMBER":
                value = {"number": float(raw_value)}
            elif data_type == "TEXT":
                value = {"text": str(raw_value)}
            elif data_type == "SINGLE_SELECT":
                option = next(
                    (
                        candidate
                        for candidate in field.get("options", [])
                        if candidate.get("name") == raw_value
                    ),
                    None,
                )
                if not option:
                    raise GitHubApiError(
                        422, f"Project field '{name}' has no option '{raw_value}'"
                    )
                value = {"singleSelectOptionId": option["id"]}
            elif data_type == "ITERATION":
                configuration = field.get("configuration") or {}
                if raw_value in {"@current", "@next"}:
                    raise GitHubApiError(
                        422,
                        f"Project iteration alias '{raw_value}' must be resolved by "
                        "a refreshed iteration plan before assignment",
                    )
                active = [
                    candidate
                    for candidate in configuration.get("iterations") or []
                    if candidate.get("title") == raw_value
                ]
                completed = [
                    candidate
                    for candidate in configuration.get("completedIterations") or []
                    if candidate.get("title") == raw_value
                ]
                if completed:
                    raise GitHubApiError(
                        422, f"Project iteration '{raw_value}' is completed"
                    )
                if len(active) > 1:
                    raise GitHubApiError(
                        422, f"Project iteration '{raw_value}' is ambiguous"
                    )
                iteration = active[0] if active else None
                if not iteration:
                    raise GitHubApiError(
                        422, f"Project field '{name}' has no iteration '{raw_value}'"
                    )
                value = {"iterationId": iteration["id"]}
            else:
                raise GitHubApiError(
                    422, f"Project field '{name}' has unsupported type '{data_type}'"
                )
            self.transport.graphql(
                """
                mutation SetField(
                  $project: ID!, $item: ID!, $field: ID!,
                  $value: ProjectV2FieldValue!
                ) {
                  updateProjectV2ItemFieldValue(input: {
                    projectId: $project, itemId: $item,
                    fieldId: $field, value: $value
                  }) { projectV2Item { id } }
                }
                """,
                {
                    "project": project_id,
                    "item": project_item_id,
                    "field": field["id"],
                    "value": value,
                },
            )


class GitHubPlanExecutor:
    """Resolve stable ABK ids and dispatch one already-reviewed sync action."""

    def __init__(
        self, service: Any, *, remote_snapshot: dict[str, Any]
    ) -> None:
        self.service = service
        self._issues: dict[str, GitHubIssueRef] = {}
        for raw in remote_snapshot.get("issues", []):
            item_id = raw.get("abk_id")
            if not item_id:
                continue
            try:
                self._issues[item_id] = GitHubIssueRef(
                    item_id=item_id,
                    number=int(raw["number"]),
                    database_id=int(raw["id"]),
                    node_id=str(raw["node_id"]),
                    url=str(raw.get("html_url") or raw.get("url") or ""),
                    project_item_id=raw.get("project_item_id"),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ManifestError(
                    f"Remote issue '{item_id}' is missing GitHub identity fields"
                ) from exc

    def _get(self, item_id: str) -> GitHubIssueRef:
        try:
            return self._issues[item_id]
        except KeyError as exc:
            raise ManifestError(
                f"Sync action references unresolved GitHub issue '{item_id}'"
            ) from exc

    def __call__(self, action: SyncAction) -> None:
        if action.kind == "issue.create":
            self._issues[action.item_id] = self.service.create_issue(
                action.item_id, action.payload
            )
        elif action.kind == "issue.update":
            self.service.update_issue(self._get(action.item_id), action.payload)
        elif action.kind == "project.add_item":
            self.service.add_project_item(
                self._get(action.item_id), action.payload["fields"]
            )
        elif action.kind == "project.set_fields":
            self.service.set_project_fields(
                self._get(action.item_id), action.payload["fields"]
            )
        elif action.kind == "issue.set_parent":
            self.service.set_parent(
                self._get(action.item_id), self._get(action.payload["parent"])
            )
        elif action.kind == "issue.add_dependency":
            self.service.add_dependency(
                self._get(action.item_id), self._get(action.payload["depends_on"])
            )
        else:
            raise ManifestError(f"Unsupported sync action kind '{action.kind}'")


class GitHubScaffoldExecutor:
    def __init__(self, service: GitHubService) -> None:
        self.service = service

    def __call__(self, action: ScaffoldAction) -> None:
        if action.kind == "project.field.create":
            self.service.create_project_field(action.payload)
        elif action.kind == "project.field.update_options":
            self.service.update_project_field_options(action.payload)
        elif action.kind == "project.field.update_iterations":
            current = action.precondition.get("field")
            configuration = action.payload.get("iteration_configuration") or {}
            if not isinstance(current, dict):
                raise ManifestError(
                    "Iteration update requires the reviewed field precondition"
                )
            if (
                (
                    current.get("id") is not None
                    and current.get("id") != action.payload.get("field_id")
                )
                or (
                    current.get("name") is not None
                    and current.get("name") != action.payload.get("name")
                )
            ):
                raise ManifestError(
                    "Iteration update does not bind the reviewed field identity"
                )
            current_configuration = current.get("iteration_configuration")
            if not isinstance(current_configuration, dict):
                raise ManifestError(
                    "Iteration update requires the reviewed field configuration"
                )
            previous = current_configuration.get("iterations") or []
            replacement = configuration.get("iterations") or []
            if replacement[: len(previous)] != previous:
                raise ManifestError(
                    "Iteration update does not preserve every observed active definition"
                )
            self.service.update_project_field_iterations(action.payload)
        elif action.kind == "repository.label.create":
            self.service.create_label(action.payload)
        elif action.kind == "project.view.create":
            self.service.create_project_view(action.payload)
        elif action.kind == "project.view.update":
            self.service.update_project_view(action.payload)
        else:
            raise ManifestError(f"Unsupported scaffold action kind '{action.kind}'")
