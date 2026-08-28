from __future__ import annotations

import unittest

from agentic_backlog_kit.github import (
    GitHubApiError,
    GitHubIssueRef,
    GitHubPlanExecutor,
    GitHubScaffoldExecutor,
    GitHubService,
)
from agentic_backlog_kit.scaffold import ScaffoldAction
from agentic_backlog_kit.sync import apply_plan, build_sync_plan

from tests.helpers import item, manifest


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.next_number = 10

    def create_issue(self, item_id: str, payload: dict) -> GitHubIssueRef:
        self.calls.append(("create_issue", item_id))
        number = self.next_number
        self.next_number += 1
        return GitHubIssueRef(
            item_id=item_id,
            number=number,
            database_id=1000 + number,
            node_id=f"ISSUE_{number}",
            url=f"https://github.com/aegolius-labs/example/issues/{number}",
        )

    def update_issue(self, issue: GitHubIssueRef, payload: dict) -> None:
        self.calls.append(("update_issue", issue.item_id, payload))

    def add_project_item(self, issue: GitHubIssueRef, fields: dict) -> None:
        self.calls.append(("add_project_item", issue.item_id, fields))

    def set_project_fields(self, issue: GitHubIssueRef, fields: dict) -> None:
        self.calls.append(("set_project_fields", issue.item_id, fields))

    def set_parent(self, child: GitHubIssueRef, parent: GitHubIssueRef) -> None:
        self.calls.append(("set_parent", child.item_id, parent.item_id))

    def add_dependency(self, issue: GitHubIssueRef, blocker: GitHubIssueRef) -> None:
        self.calls.append(("add_dependency", issue.item_id, blocker.item_id))


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.responses: list[object] = []

    def rest(self, method: str, path: str, payload: dict | None = None):
        self.calls.append((method, path, payload))
        response = self.responses.pop(0) if self.responses else {}
        if isinstance(response, Exception):
            raise response
        return response

    def graphql(self, query: str, variables: dict):
        self.calls.append(("GRAPHQL", variables))
        response = self.responses.pop(0) if self.responses else {}
        if isinstance(response, Exception):
            raise response
        return response


class GitHubExecutorTests(unittest.TestCase):
    def test_created_issue_ids_are_available_to_later_relationship_actions(self) -> None:
        data = manifest(item("T-BASE"), item("T-VALUE", depends_on=["T-BASE"]))
        plan = build_sync_plan(data, {"issues": []})
        service = FakeService()
        executor = GitHubPlanExecutor(service, remote_snapshot={"issues": []})

        apply_plan(
            plan,
            executor=executor,
            confirmation=plan.digest,
            manifest=data,
            remote_snapshot={"issues": []},
        )

        self.assertEqual(
            [
                "create_issue",
                "create_issue",
                "add_project_item",
                "add_project_item",
                "add_dependency",
            ],
            [call[0] for call in service.calls],
        )
        self.assertEqual(("add_dependency", "T-VALUE", "T-BASE"), service.calls[-1])

    def test_snapshot_seeds_existing_issue_identity(self) -> None:
        service = FakeService()
        snapshot = {
            "issues": [
                {
                    "abk_id": "T-1",
                    "number": 7,
                    "id": 700,
                    "node_id": "ISSUE_7",
                    "url": "https://github.com/aegolius-labs/example/issues/7",
                }
            ]
        }
        executor = GitHubPlanExecutor(service, remote_snapshot=snapshot)

        from agentic_backlog_kit.sync import SyncAction

        executor(SyncAction("issue.update", "T-1", {"title": "New title"}))

        self.assertEqual("T-1", service.calls[0][1])


class GitHubServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeTransport()
        self.service = GitHubService(
            self.transport,
            owner="aegolius-labs",
            repository="example",
            project_number=1,
            issue_type_mode="native_or_label",
        )
        self.child = GitHubIssueRef("T-1", 11, 111, "NODE_11", "child-url")
        self.parent = GitHubIssueRef("F-1", 7, 77, "NODE_7", "parent-url")

    def test_uses_current_rest_endpoints_for_hierarchy_and_dependencies(self) -> None:
        self.service.set_parent(self.child, self.parent)
        self.service.add_dependency(self.child, self.parent)

        self.assertEqual(
            (
                "POST",
                "/repos/aegolius-labs/example/issues/7/sub_issues",
                {"sub_issue_id": 111, "replace_parent": True},
            ),
            self.transport.calls[0],
        )
        self.assertEqual(
            (
                "POST",
                "/repos/aegolius-labs/example/issues/11/dependencies/blocked_by",
                {"issue_id": 77},
            ),
            self.transport.calls[1],
        )

    def test_native_or_label_retries_issue_creation_with_a_type_label(self) -> None:
        self.transport.responses = [
            GitHubApiError(422, "Unknown issue type"),
            {
                "number": 12,
                "id": 1200,
                "node_id": "NODE_12",
                "html_url": "issue-url",
            },
        ]

        issue = self.service.create_issue(
            "T-1",
            {
                "title": "Task",
                "body": "Body",
                "type": "Task",
                "fallback_label": "type:task",
            },
        )

        self.assertEqual(12, issue.number)
        self.assertEqual(["type:task"], self.transport.calls[1][2]["labels"])
        self.assertNotIn("type", self.transport.calls[1][2])

    def test_type_update_fallback_preserves_unmanaged_labels(self) -> None:
        self.transport.responses = [GitHubApiError(422, "Unknown issue type"), {}]

        self.service.update_issue(
            self.child,
            {
                "type": "Task",
                "fallback_label": "type:task",
                "labels": ["customer", "type:task"],
            },
        )

        self.assertEqual(
            {"labels": ["customer", "type:task"]}, self.transport.calls[1][2]
        )

    def test_scaffold_executor_updates_single_select_options(self) -> None:
        action = ScaffoldAction(
            "project.field.update_options",
            {
                "name": "Status",
                "field_id": "FIELD_STATUS",
                "options": [
                    {
                        "id": "todo-id",
                        "name": "Todo",
                        "color": "GRAY",
                        "description": "Existing",
                    },
                    {
                        "name": "Ready",
                        "color": "BLUE",
                        "description": "",
                    },
                ],
            },
        )

        GitHubScaffoldExecutor(self.service)(action)

        query_call = self.transport.calls[0]
        self.assertEqual("GRAPHQL", query_call[0])
        self.assertEqual("FIELD_STATUS", query_call[1]["input"]["fieldId"])
        self.assertEqual("todo-id", query_call[1]["input"]["singleSelectOptions"][0]["id"])


if __name__ == "__main__":
    unittest.main()
