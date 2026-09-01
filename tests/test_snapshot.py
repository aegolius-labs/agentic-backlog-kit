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
        self.graphql_calls: list[tuple[str, dict]] = []

    def rest(self, method: str, path: str, payload=None):
        response = self.rest_responses[(method, path)]
        if isinstance(response, Exception):
            raise response
        return response

    def graphql(self, query: str, variables: dict):
        self.graphql_calls.append((query, variables))
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
    def test_discovers_shallow_projects_then_hydrates_only_selected_project(self) -> None:
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
                            },
                            {
                                "id": "PROJECT_7",
                                "number": 7,
                                "title": "Selected",
                                "url": "url-7",
                                "closed": False,
                            },
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
                "repository": {
                    "id": "REPO_1",
                    "name": "example",
                    "projectsV2": {
                        "nodes": [{"id": "PROJECT_7"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
            {
                "organization": {
                    "projectV2": {
                        "fields": {
                            "nodes": [
                                {
                                    "id": "FIELD_EFFORT",
                                    "databaseId": 42,
                                    "name": "Effort",
                                    "dataType": "NUMBER",
                                }
                            ]
                        },
                        "views": {"nodes": []},
                    }
                }
            },
        ]
        transport.rest_responses[
            ("GET", "/repos/aegolius-labs/example/labels?per_page=100&page=1")
        ] = []

        result = GitHubProjectDiscoveryReader(
            transport,
            owner="aegolius-labs",
            repository="example",
            project_number=7,
        ).read()

        discovery_query, discovery_variables = transport.graphql_calls[0]
        self.assertNotIn("fields(first:", discovery_query)
        self.assertNotIn("views(first:", discovery_query)
        self.assertNotIn("visibleFields(first:", discovery_query)
        self.assertEqual(
            {"owner": "aegolius-labs", "repository": "example"},
            discovery_variables,
        )
        hydration_query, hydration_variables = transport.graphql_calls[1]
        self.assertIn("query ProjectScaffold", hydration_query)
        self.assertEqual(
            {"owner": "aegolius-labs", "number": 7}, hydration_variables
        )
        self.assertEqual([], result["projects"][0]["fields"])
        self.assertEqual("Effort", result["projects"][1]["fields"][0]["name"])
        self.assertEqual([], result["projects"][1]["views"])

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
        # Responses captured from the legacy deep discovery query remain parseable,
        # even though current discovery no longer requests nested scaffold state.
        self.assertNotIn("fields(first:", transport.graphql_calls[0][0])

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
            {
                "organization": {
                    "projectV2": {
                        "fields": {"nodes": []},
                        "views": {"nodes": []},
                    }
                }
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
    def test_reads_empty_github_iteration_configuration_without_fabricating_schedule(self) -> None:
        transport = RoutedTransport()
        transport.graphql_responses = [
            {
                "organization": {
                    "projectV2": {
                        "fields": {
                            "nodes": [
                                {
                                    "id": "FIELD_SPRINT",
                                    "databaseId": 103,
                                    "name": "Sprint",
                                    "dataType": "ITERATION",
                                    "configuration": {
                                        "duration": 14,
                                        "iterations": [],
                                        "completedIterations": [],
                                    },
                                }
                            ]
                        },
                        "views": {"nodes": []},
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

        field = snapshot["fields"][0]
        self.assertEqual("FIELD_SPRINT", field["id"])
        self.assertIsNone(field["iteration_configuration"]["start_date"])
        self.assertEqual([], field["iteration_configuration"]["iterations"])

    def test_reads_complete_view_configuration_with_field_identities(self) -> None:
        transport = RoutedTransport()
        status = {
            "id": "FIELD_STATUS",
            "databaseId": "101",
            "name": "Status",
        }
        priority = {
            "id": "FIELD_PRIORITY",
            "databaseId": "102",
            "name": "Priority",
        }
        transport.graphql_responses = [
            {
                "organization": {
                    "projectV2": {
                        "fields": {
                            "nodes": [
                                {
                                    "id": "FIELD_SPRINT",
                                    "databaseId": "103",
                                    "name": "Sprint",
                                    "dataType": "ITERATION",
                                    "configuration": {
                                        "duration": 14,
                                        "startDay": 1,
                                        "iterations": [
                                            {
                                                "id": "ITER_1",
                                                "title": "Sprint 1",
                                                "startDate": "2026-08-17",
                                                "duration": 14,
                                            }
                                        ],
                                        "completedIterations": [],
                                    },
                                }
                            ]
                        },
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
        iteration_field = snapshot["fields"][0]
        self.assertEqual(103, iteration_field["database_id"])
        self.assertEqual(
            "ITER_1",
            iteration_field["iteration_configuration"]["iterations"][0]["id"],
        )
        self.assertIn("databaseId", transport.graphql_calls[0][0])
        self.assertNotIn("fullDatabaseId", transport.graphql_calls[0][0])


if __name__ == "__main__":
    unittest.main()
