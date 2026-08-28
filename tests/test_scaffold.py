from __future__ import annotations

import unittest

from agentic_backlog_kit.manifest import ManifestError
from agentic_backlog_kit.scaffold import (
    ScaffoldAuthorizationError,
    apply_scaffold_plan,
    build_scaffold_plan,
)

from tests.helpers import manifest


VIEW_FIELDS = [
    "Title",
    "Status",
    "Sprint",
    "Impact",
    "Effort",
    "Business Value",
    "Enabler Value",
    "Priority",
]


def project_fields() -> list[dict]:
    result = []
    for index, name in enumerate(VIEW_FIELDS, start=1):
        data_type = "NUMBER"
        options = []
        if name == "Title":
            data_type = "TITLE"
        elif name == "Status":
            data_type = "SINGLE_SELECT"
            options = [
                {
                    "id": f"OPTION_{option_index}",
                    "name": option,
                    "color": "GRAY",
                    "description": "",
                }
                for option_index, option in enumerate(manifest()["workflow"]["statuses"])
            ]
        elif name == "Sprint":
            data_type = "ITERATION"
        result.append(
            {
                "id": f"FIELD_{index}",
                "database_id": 1000 + index,
                "name": name,
                "data_type": data_type,
                "options": options,
            }
        )
    return result


class ScaffoldPlanningTests(unittest.TestCase):
    def test_empty_project_gets_fields_labels_and_four_agile_views(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }

        plan = build_scaffold_plan(
            data, {"fields": [], "views": [], "labels": []}
        )

        kinds = [action.kind for action in plan.actions]
        self.assertEqual(7, kinds.count("project.field.create"))
        self.assertEqual(6, kinds.count("repository.label.create"))
        self.assertEqual(4, kinds.count("project.view.create"))
        self.assertEqual(
            ["Backlog", "Kanban", "Current Sprint", "Roadmap"],
            [
                action.payload["name"]
                for action in plan.actions
                if action.kind == "project.view.create"
            ],
        )

    def test_matching_scaffold_is_idempotent(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        initial = {"fields": project_fields(), "views": [], "labels": []}
        first = build_scaffold_plan(data, initial)
        snapshot = {
            "fields": project_fields(),
            "views": [
                {**action.payload, "id": f"VIEW_{index}", "number": index}
                for index, action in enumerate(first.actions, start=1)
                if action.kind == "project.view.create"
            ],
            "labels": [
                {"name": action.payload["name"]}
                for action in first.actions
                if action.kind == "repository.label.create"
            ],
        }

        second = build_scaffold_plan(data, snapshot)

        self.assertEqual([], second.actions)

    def test_supported_same_name_view_drift_produces_reviewed_update(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        fields = project_fields()
        created = build_scaffold_plan(
            data, {"fields": fields, "views": [], "labels": []}
        )
        backlog = next(
            action.payload
            for action in created.actions
            if action.kind == "project.view.create" and action.payload["name"] == "Backlog"
        )
        current = {
            **backlog,
            "id": "VIEW_BACKLOG",
            "number": 1,
            "layout": "board",
            "filter": "is:issue is:open",
            "visible_fields": list(reversed(backlog["visible_fields"])),
        }

        plan = build_scaffold_plan(
            data, {"fields": fields, "views": [current], "labels": []}
        )

        update = next(action for action in plan.actions if action.kind == "project.view.update")
        self.assertEqual("VIEW_BACKLOG", update.payload["view_id"])
        self.assertEqual("table", update.payload["layout"])
        self.assertEqual("is:issue", update.payload["filter"])
        self.assertEqual(backlog["visible_fields"], update.payload["visible_fields"])
        self.assertEqual(current, update.precondition["view"])

        equivalent = {**backlog, "id": "VIEW_BACKLOG", "number": 1}
        converged = build_scaffold_plan(
            data, {"fields": fields, "views": [equivalent], "labels": []}
        )
        self.assertFalse(
            any(
                action.kind == "project.view.update"
                and action.payload["name"] == "Backlog"
                for action in converged.actions
            )
        )

    def test_unsupported_group_or_sort_drift_fails_closed_precisely(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        fields = project_fields()
        created = build_scaffold_plan(
            data, {"fields": fields, "views": [], "labels": []}
        )
        backlog = next(
            action.payload
            for action in created.actions
            if action.kind == "project.view.create" and action.payload["name"] == "Backlog"
        )
        current = {
            **backlog,
            "id": "VIEW_BACKLOG",
            "number": 1,
            "sort_by": [],
        }

        with self.assertRaisesRegex(
            ManifestError, "Backlog.*sort_by.*cannot update.*GitHub API"
        ):
            build_scaffold_plan(
                data, {"fields": fields, "views": [current], "labels": []}
            )

    def test_incompatible_existing_field_fails_closed(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }

        with self.assertRaisesRegex(ManifestError, "Impact.*TEXT.*NUMBER"):
            build_scaffold_plan(
                data,
                {
                    "fields": [{"name": "Impact", "data_type": "TEXT"}],
                    "views": [],
                    "labels": [],
                },
            )

    def test_existing_status_field_is_extended_without_replacing_option_ids(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        existing = [
            {
                "id": "status-todo",
                "name": "Todo",
                "color": "GRAY",
                "description": "Existing project default",
            },
            {
                "id": "status-done",
                "name": "Done",
                "color": "GREEN",
                "description": "Existing project default",
            },
        ]

        plan = build_scaffold_plan(
            data,
            {
                "fields": [
                    {
                        "id": "status-field",
                        "name": "Status",
                        "data_type": "SINGLE_SELECT",
                        "options": existing,
                    }
                ],
                "views": [],
                "labels": [],
            },
        )

        action = next(
            action
            for action in plan.actions
            if action.kind == "project.field.update_options"
        )
        self.assertEqual("status-field", action.payload["field_id"])
        self.assertEqual(
            ["status-todo", "status-done"],
            [option["id"] for option in action.payload["options"][:2]],
        )
        self.assertTrue(
            set(data["workflow"]["statuses"]).issubset(
                {option["name"] for option in action.payload["options"]}
            )
        )

    def test_apply_requires_exact_plan_digest(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        plan = build_scaffold_plan(data, {"fields": [], "views": [], "labels": []})

        with self.assertRaises(ScaffoldAuthorizationError):
            apply_scaffold_plan(plan, executor=lambda action: None, confirmation="wrong")

    def test_scaffold_apply_aborts_on_fresh_state_drift(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        snapshot = {"fields": [], "views": [], "labels": []}
        plan = build_scaffold_plan(data, snapshot)
        writes = []
        drifted = {"fields": [], "views": [], "labels": [{"name": "type:task"}]}

        with self.assertRaisesRegex(ScaffoldAuthorizationError, "drift"):
            apply_scaffold_plan(
                plan,
                executor=writes.append,
                confirmation=plan.digest,
                manifest=data,
                project_snapshot=drifted,
            )
        self.assertEqual([], writes)

    def test_scaffold_failure_journals_completed_prefix(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        snapshot = {"fields": [], "views": [], "labels": []}
        plan = build_scaffold_plan(data, snapshot)
        journal = []
        calls = 0

        def fail_second(action):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected scaffold failure")

        with self.assertRaisesRegex(RuntimeError, "injected scaffold failure"):
            apply_scaffold_plan(
                plan,
                executor=fail_second,
                confirmation=plan.digest,
                manifest=data,
                project_snapshot=snapshot,
                journal=journal.append,
            )
        self.assertEqual("failed", journal[-1].status)
        self.assertEqual(1, journal[-1].applied_actions)
        self.assertEqual(plan.actions[1].as_dict(), journal[-1].failed_action)


if __name__ == "__main__":
    unittest.main()
