from __future__ import annotations

import unittest

from agentic_backlog_kit.github import GitHubApiError
from agentic_backlog_kit.snapshot import (
    GitHubProjectDiscoveryReader,
    GitHubScaffoldSnapshotReader,
    GitHubSnapshotReader,
)


class RoutedTransport:
    def __init__(self) -> None:
        self.rest_responses: dict[tuple[str, str], object] = {}
        self.graphql_responses: list[dict] = []

    def rest(self, method: str, path: str, payload=None):
        response = self.rest_responses[(method, path)]
        if isinstance(response, Exception):
            raise response
        return response

    def graphql(self, query: str, variables: dict):
        return self.graphql_responses.pop(0)


class SnapshotReaderTests(unittest.TestCase):
    def test_reads_managed_issues_relationships_and_project_fields(self) -> None:
        transport = RoutedTransport()
        issues_path = "/repos/aegolius-labs/example/issues?state=all&per_page=100&page=1"
        base = {
            "id": 101,
            "node_id": "NODE_1",
            "number": 1,
            "html_url": "issue-1",
            "title": "Base",
            "body": "<!-- agentic-backlog-kit:id=T-BASE;schema=1 -->",
            "state": "open",
            "type": None,
            "labels": [{"name": "customer"}, {"name": "type:task"}],
        }
        value = {
            "id": 102,
            "node_id": "NODE_2",
            "number": 2,
            "html_url": "issue-2",
            "title": "Value",
            "body": "<!-- agentic-backlog-kit:id=T-VALUE;schema=1 -->",
            "state": "open",
            "type": {"name": "Task"},
        }
        transport.rest_responses[("GET", issues_path)] = [base, value]
        transport.rest_responses[("GET", "/repos/aegolius-labs/example/issues/1/parent")] = GitHubApiError(404, "No parent")
        transport.rest_responses[("GET", "/repos/aegolius-labs/example/issues/1/dependencies/blocked_by?per_page=100")] = []
        transport.rest_responses[("GET", "/repos/aegolius-labs/example/issues/2/parent")] = base
        transport.rest_responses[("GET", "/repos/aegolius-labs/example/issues/2/dependencies/blocked_by?per_page=100")] = [base]
        transport.graphql_responses = [
            {
                "organization": {
                    "projectV2": {
                        "items": {
                            "nodes": [
                                {
                                    "id": "PITEM_2",
                                    "content": {"id": "NODE_2", "number": 2, "repository": {"nameWithOwner": "aegolius-labs/example"}},
                                    "fieldValues": {
                                        "nodes": [
                                            {"field": {"name": "Status"}, "name": "Ready"},
                                            {"field": {"name": "Effort"}, "number": 3.0},
                                        ]
                                    },
                                }
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }
        ]

        snapshot = GitHubSnapshotReader(
            transport,
            owner="aegolius-labs",
            repository="example",
            project_number=1,
        ).read()

        by_id = {issue["abk_id"]: issue for issue in snapshot["issues"]}
        self.assertEqual("T-BASE", by_id["T-VALUE"]["parent_abk_id"])
        self.assertEqual(["T-BASE"], by_id["T-VALUE"]["depends_on_abk_ids"])
        self.assertEqual("Ready", by_id["T-VALUE"]["project_fields"]["Status"])
        self.assertTrue(by_id["T-VALUE"]["in_project"])
        self.assertFalse(by_id["T-BASE"]["in_project"])
        self.assertEqual("Task", by_id["T-BASE"]["type"])
        self.assertEqual(["customer", "type:task"], by_id["T-BASE"]["labels"])


class ProjectDiscoveryReaderTests(unittest.TestCase):
    def test_normalizes_full_iteration_configuration(self) -> None:
        transport = RoutedTransport()
        transport.graphql_responses = [
            {
                "organization": {
                    "id": "ORG_1",
                    "projectsV2": {
                        "nodes": [
                            {
                                "id": "PROJECT_2",
                                "number": 2,
                                "title": "First",
                                "url": "url-2",
                                "closed": False,
                                "fields": {
                                    "nodes": [
                                        {
                                            "id": "FIELD_SPRINT",
                                            "databaseId": 42,
                                            "name": "Sprint",
                                            "dataType": "ITERATION",
                                            "configuration": {
                                                "duration": 14,
                                                "startDay": 1,
                                                "iterations": [
                                                    {
                                                        "id": "ITER_10",
                                                        "title": "Sprint 10",
                                                        "startDate": "2026-08-17",
                                                        "duration": 14,
                                                    }
                                                ],
                                                "completedIterations": [],
                                            },
                                        }
                                    ]
                                },
                                "views": {"nodes": []},
                            }
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
                "repository": {
                    "id": "REPO_1",
                    "projectsV2": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            }
        ]
        transport.rest_responses[
            ("GET", "/repos/aegolius-labs/example/labels?per_page=100&page=1")
        ] = []

        result = GitHubProjectDiscoveryReader(
            transport, owner="aegolius-labs", repository="example"
        ).read()

        field = result["projects"][0]["fields"][0]
        self.assertEqual("2026-08-17", field["iteration_configuration"]["start_date"])
        self.assertEqual("ITER_10", field["iteration_configuration"]["iterations"][0]["id"])

    def test_reads_sorted_projects_and_marks_repository_links(self) -> None:
        transport = RoutedTransport()
        transport.graphql_responses = [
            {
                "organization": {
                    "id": "ORG_1",
                    "projectsV2": {
                        "nodes": [
                            {
                                "id": "PROJECT_7",
                                "number": 7,
                                "title": "Later",
                                "url": "url-7",
                                "closed": False,
                                "fields": {"nodes": []},
                                "views": {"nodes": []},
                            },
                            {
                                "id": "PROJECT_2",
                                "number": 2,
                                "title": "First",
                                "url": "url-2",
                                "closed": False,
                                "fields": {"nodes": []},
                                "views": {"nodes": []},
                            },
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
                "repository": {
                    "id": "REPO_1",
                    "projectsV2": {
                        "nodes": [{"id": "PROJECT_7"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        ]
        transport.rest_responses[
            ("GET", "/repos/aegolius-labs/example/labels?per_page=100&page=1")
        ] = []

        result = GitHubProjectDiscoveryReader(
            transport, owner="aegolius-labs", repository="example"
        ).read()

        self.assertEqual([2, 7], [entry["number"] for entry in result["projects"]])
        self.assertFalse(result["projects"][0]["linked"])
        self.assertTrue(result["projects"][1]["linked"])
        self.assertEqual("ORG_1", result["organization"]["id"])


class ScaffoldSnapshotReaderTests(unittest.TestCase):
    def test_reads_complete_view_configuration_with_field_identities(self) -> None:
        transport = RoutedTransport()
        status = {
            "id": "FIELD_STATUS",
            "fullDatabaseId": "101",
            "name": "Status",
        }
        priority = {
            "id": "FIELD_PRIORITY",
            "fullDatabaseId": "102",
            "name": "Priority",
        }
        transport.graphql_responses = [
            {
                "organization": {
                    "projectV2": {
                        "fields": {"nodes": []},
                        "views": {
                            "nodes": [
                                {
                                    "id": "VIEW_BACKLOG",
                                    "number": 1,
                                    "name": "Backlog",
                                    "layout": "TABLE_LAYOUT",
                                    "filter": "is:issue",
                                    "configuration": {
                                        "visibleFields": {
                                            "nodes": [status, priority],
                                            "pageInfo": {"hasNextPage": False},
                                        }
                                    },
                                    "groupByFields": {
                                        "nodes": [],
                                        "pageInfo": {"hasNextPage": False},
                                    },
                                    "verticalGroupByFields": {
                                        "nodes": [],
                                        "pageInfo": {"hasNextPage": False},
                                    },
                                    "sortByFields": {
                                        "nodes": [
                                            {"field": priority, "direction": "DESC"}
                                        ],
                                        "pageInfo": {"hasNextPage": False},
                                    },
                                }
                            ]
                        },
                    }
                }
            }
        ]
        transport.rest_responses[
            ("GET", "/repos/aegolius-labs/example/labels?per_page=100&page=1")
        ] = []

        snapshot = GitHubScaffoldSnapshotReader(
            transport,
            owner="aegolius-labs",
            repository="example",
            project_number=1,
        ).read()

        view = snapshot["views"][0]
        self.assertEqual("VIEW_BACKLOG", view["id"])
        self.assertEqual(["Status", "Priority"], [entry["name"] for entry in view["visible_fields"]])
        self.assertEqual(102, view["sort_by"][0]["field"]["database_id"])
        self.assertEqual("desc", view["sort_by"][0]["direction"])


if __name__ == "__main__":
    unittest.main()
