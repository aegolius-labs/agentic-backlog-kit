from __future__ import annotations

import unittest

from agentic_backlog_kit.manifest import ManifestError
from agentic_backlog_kit.views import (
    expected_view_specs,
    normalize_project_views,
    resolve_view_spec,
)


def field(name: str, number: int) -> dict:
    return {
        "id": f"FIELD_{number}",
        "fullDatabaseId": str(1000 + number),
        "name": name,
    }


class ViewNormalizationTests(unittest.TestCase):
    def test_normalizes_complete_configuration_and_preserves_configured_order(self) -> None:
        status = field("Status", 1)
        priority = field("Priority", 2)
        project = {
            "views": {
                "nodes": [
                    {
                        "id": "VIEW_2",
                        "number": 2,
                        "name": "Kanban",
                        "layout": "BOARD_LAYOUT",
                        "filter": " is:issue   is:open ",
                        "configuration": {
                            "visibleFields": {
                                "nodes": [priority, status],
                                "pageInfo": {"hasNextPage": False},
                            }
                        },
                        "groupByFields": {
                            "nodes": [],
                            "pageInfo": {"hasNextPage": False},
                        },
                        "verticalGroupByFields": {
                            "nodes": [status],
                            "pageInfo": {"hasNextPage": False},
                        },
                        "sortByFields": {
                            "nodes": [
                                {"field": priority, "direction": "DESC"},
                                {"field": status, "direction": "ASC"},
                            ],
                            "pageInfo": {"hasNextPage": False},
                        },
                    }
                ]
            }
        }

        views = normalize_project_views(project)

        self.assertEqual("board", views[0]["layout"])
        self.assertEqual("is:issue is:open", views[0]["filter"])
        self.assertEqual(
            ["Priority", "Status"],
            [entry["name"] for entry in views[0]["visible_fields"]],
        )
        self.assertEqual(["Status"], [entry["name"] for entry in views[0]["vertical_group_by"]])
        self.assertEqual(
            [("Priority", "desc"), ("Status", "asc")],
            [
                (entry["field"]["name"], entry["direction"])
                for entry in views[0]["sort_by"]
            ],
        )

    def test_sorts_views_but_does_not_sort_ordered_view_configuration(self) -> None:
        def raw_view(name: str, number: int) -> dict:
            return {
                "id": f"VIEW_{number}",
                "number": number,
                "name": name,
                "layout": "TABLE_LAYOUT",
                "filter": "",
                "configuration": {"visibleFields": {"nodes": [], "pageInfo": {"hasNextPage": False}}},
                "groupByFields": {"nodes": [], "pageInfo": {"hasNextPage": False}},
                "verticalGroupByFields": {"nodes": [], "pageInfo": {"hasNextPage": False}},
                "sortByFields": {"nodes": [], "pageInfo": {"hasNextPage": False}},
            }

        result = normalize_project_views(
            {"views": {"nodes": [raw_view("Roadmap", 4), raw_view("Backlog", 1)]}}
        )

        self.assertEqual(["Backlog", "Roadmap"], [view["name"] for view in result])

    def test_rejects_truncated_configuration_instead_of_comparing_partial_state(self) -> None:
        raw = {
            "views": {
                "nodes": [
                    {
                        "id": "VIEW_1",
                        "number": 1,
                        "name": "Backlog",
                        "layout": "TABLE_LAYOUT",
                        "configuration": {
                            "visibleFields": {
                                "nodes": [],
                                "pageInfo": {"hasNextPage": True},
                            }
                        },
                        "groupByFields": {"nodes": [], "pageInfo": {"hasNextPage": False}},
                        "verticalGroupByFields": {"nodes": [], "pageInfo": {"hasNextPage": False}},
                        "sortByFields": {"nodes": [], "pageInfo": {"hasNextPage": False}},
                    }
                ]
            }
        }

        with self.assertRaisesRegex(ManifestError, "Backlog.*visible fields.*truncated"):
            normalize_project_views(raw)


class DesiredViewTests(unittest.TestCase):
    def test_resolves_names_to_both_github_id_forms(self) -> None:
        fields = [
            {
                "id": f"FIELD_{index}",
                "database_id": 2000 + index,
                "name": name,
                "data_type": "NUMBER",
            }
            for index, name in enumerate(
                [
                    "Title",
                    "Status",
                    "Sprint",
                    "Priority",
                    "Impact",
                    "Effort",
                    "Business Value",
                    "Enabler Value",
                ]
            )
        ]
        backlog = expected_view_specs("Sprint")[0]

        resolved = resolve_view_spec(backlog, fields, require_ids=True)

        self.assertEqual("FIELD_0", resolved["visible_fields"][0]["id"])
        self.assertEqual(2003, resolved["sort_by"][0]["field"]["database_id"])
        self.assertEqual("desc", resolved["sort_by"][0]["direction"])

    def test_missing_identity_fails_closed_when_existing_view_needs_comparison(self) -> None:
        with self.assertRaisesRegex(ManifestError, "Status.*identity"):
            resolve_view_spec(
                {
                    "name": "Kanban",
                    "layout": "board",
                    "filter": "is:issue",
                    "visible_fields": ["Status"],
                    "group_by": [],
                    "vertical_group_by": [],
                    "sort_by": [],
                },
                [{"name": "Status", "data_type": "SINGLE_SELECT"}],
                require_ids=True,
            )


if __name__ == "__main__":
    unittest.main()
