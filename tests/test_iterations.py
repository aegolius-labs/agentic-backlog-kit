from __future__ import annotations

import unittest

from agentic_backlog_kit.iterations import (
    IterationAuthorizationError,
    apply_iteration_plan,
    build_iteration_plan,
    discover_iterations,
    normalize_iteration_field,
    verify_iteration_apply,
)
from agentic_backlog_kit.manifest import ManifestError

from tests.helpers import manifest


def iteration_field(
    *,
    active: list[dict] | None = None,
    completed: list[dict] | None = None,
    duration: int = 14,
) -> dict:
    return {
        "id": "FIELD_SPRINT",
        "database_id": 42,
        "name": "Sprint",
        "data_type": "ITERATION",
        "iteration_configuration": {
            "start_date": "2026-08-03",
            "duration_days": duration,
            "iterations": active
            if active is not None
            else [
                {
                    "id": "ITER_10",
                    "title": "Sprint 10",
                    "start_date": "2026-08-17",
                    "duration_days": 14,
                    "completed": False,
                },
                {
                    "id": "ITER_11",
                    "title": "Sprint 11",
                    "start_date": "2026-08-31",
                    "duration_days": 14,
                    "completed": False,
                },
            ],
            "completed_iterations": completed
            if completed is not None
            else [
                {
                    "id": "ITER_9",
                    "title": "Sprint 9",
                    "start_date": "2026-08-03",
                    "duration_days": 14,
                    "completed": True,
                }
            ],
        },
    }


def project_snapshot(field: dict | None = None) -> dict:
    return {"fields": [field or iteration_field()], "views": [], "labels": []}


class IterationNormalizationTests(unittest.TestCase):
    def test_normalizes_github_empty_iteration_configuration(self) -> None:
        # Exact shape returned after GitHub creates an ITERATION field while
        # ignoring the requested empty iterationConfiguration.
        normalized = normalize_iteration_field(
            {
                "id": "FIELD_SPRINT",
                "databaseId": 42,
                "name": "Sprint",
                "dataType": "ITERATION",
                "configuration": {
                    "duration": 14,
                    "iterations": [],
                    "completedIterations": [],
                },
            }
        )

        configuration = normalized["iteration_configuration"]
        self.assertIsNone(configuration["start_date"])
        self.assertEqual(14, configuration["duration_days"])
        self.assertEqual([], configuration["iterations"])
        self.assertEqual([], configuration["completed_iterations"])

    def test_normalizes_direct_api_uninitialized_iteration_with_zero_duration(self) -> None:
        # The direct GitHub API can report the same newly-created, uninitialized
        # field with a null start and a zero duration.
        normalized = normalize_iteration_field(
            {
                "id": "FIELD_SPRINT",
                "databaseId": 42,
                "name": "Sprint",
                "dataType": "ITERATION",
                "configuration": {
                    "duration": 0,
                    "startDay": 1,
                    "iterations": [],
                    "completedIterations": [],
                },
            }
        )

        configuration = normalized["iteration_configuration"]
        self.assertIsNone(configuration["start_date"])
        self.assertEqual(0, configuration["duration_days"])
        self.assertEqual([], configuration["iterations"])
        self.assertEqual([], configuration["completed_iterations"])

    def test_rejects_zero_or_negative_duration_outside_uninitialized_state(self) -> None:
        initialized = {
            "id": "FIELD_SPRINT",
            "name": "Sprint",
            "data_type": "ITERATION",
            "iteration_configuration": {
                "start_date": "2026-09-07",
                "duration_days": 0,
                "iterations": [],
                "completed_iterations": [],
            },
        }
        with self.assertRaisesRegex(ManifestError, "duration_days"):
            normalize_iteration_field(initialized)

        negative = {
            "id": "FIELD_SPRINT",
            "name": "Sprint",
            "data_type": "ITERATION",
            "iteration_configuration": {
                "start_date": None,
                "duration_days": -1,
                "iterations": [],
                "completed_iterations": [],
            },
        }
        with self.assertRaisesRegex(ManifestError, "duration_days"):
            normalize_iteration_field(negative)

        nonempty = {
            "id": "FIELD_SPRINT",
            "name": "Sprint",
            "data_type": "ITERATION",
            "iteration_configuration": {
                "start_date": None,
                "duration_days": 0,
                "iterations": [
                    {
                        "id": "ITER_1",
                        "title": "Sprint 1",
                        "start_date": "2026-09-07",
                        "duration_days": 14,
                    }
                ],
                "completed_iterations": [],
            },
        }
        with self.assertRaisesRegex(ManifestError, "duration_days"):
            normalize_iteration_field(nonempty)

    def test_normalizes_raw_graphql_configuration_with_completion_state(self) -> None:
        normalized = normalize_iteration_field(
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
                    "completedIterations": [
                        {
                            "id": "ITER_9",
                            "title": "Sprint 9",
                            "startDate": "2026-08-03",
                            "duration": 14,
                        }
                    ],
                },
            }
        )

        self.assertEqual("2026-08-03", normalized["iteration_configuration"]["start_date"])
        self.assertFalse(
            normalized["iteration_configuration"]["iterations"][0]["completed"]
        )
        self.assertTrue(
            normalized["iteration_configuration"]["completed_iterations"][0]["completed"]
        )

    def test_discovers_completed_current_and_upcoming_deterministically(self) -> None:
        lifecycle = discover_iterations(iteration_field(), as_of="2026-08-27")

        self.assertEqual(["Sprint 9"], [item["title"] for item in lifecycle["completed"]])
        self.assertEqual("Sprint 10", lifecycle["current"]["title"])
        self.assertEqual(["Sprint 11"], [item["title"] for item in lifecycle["upcoming"]])


class IterationPlanningTests(unittest.TestCase):
    def test_initializes_empty_field_from_explicit_title_and_manifest_schedule(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        empty = iteration_field(active=[], completed=[])
        empty["iteration_configuration"]["start_date"] = None

        plan = build_iteration_plan(
            data, project_snapshot(empty), target="Sprint 1", as_of="2026-09-07"
        )

        self.assertEqual("Sprint 1", plan.resolved_title)
        self.assertIsNone(plan.resolved_iteration_id)
        self.assertFalse(plan.ready)
        self.assertEqual(["project.field.update_iterations"], [action.kind for action in plan.actions])
        action = plan.actions[0]
        self.assertEqual(
            {
                "id": "FIELD_SPRINT",
                "database_id": 42,
                "name": "Sprint",
                "data_type": "ITERATION",
                "iteration_configuration": {
                    "start_date": None,
                    "duration_days": 14,
                    "iterations": [],
                    "completed_iterations": [],
                },
            },
            action.precondition["field"],
        )
        self.assertEqual(
            {
                "start_date": "2026-09-07",
                "duration_days": 14,
                "iterations": [
                    {
                        "id": None,
                        "title": "Sprint 1",
                        "start_date": "2026-09-07",
                        "duration_days": 14,
                        "completed": False,
                    }
                ],
                "completed_iterations": [],
            },
            action.payload["iteration_configuration"],
        )

    def test_initializes_zero_duration_empty_field_with_manifest_duration(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        empty = iteration_field(active=[], completed=[])
        empty["iteration_configuration"]["start_date"] = None
        empty["iteration_configuration"]["duration_days"] = 0

        plan = build_iteration_plan(
            data, project_snapshot(empty), target="Sprint 1", as_of="2026-09-07"
        )

        configuration = plan.actions[0].payload["iteration_configuration"]
        self.assertEqual(14, configuration["duration_days"])
        self.assertEqual([14], [entry["duration_days"] for entry in configuration["iterations"]])
        self.assertEqual(0, plan.actions[0].precondition["field"]["iteration_configuration"]["duration_days"])

    def test_initializes_empty_field_for_deterministic_current_and_next_aliases(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        empty = iteration_field(active=[], completed=[])
        empty["iteration_configuration"]["start_date"] = None

        current = build_iteration_plan(
            data, project_snapshot(empty), target="@current", as_of="2026-09-07"
        )
        next_plan = build_iteration_plan(
            data, project_snapshot(empty), target="@next", as_of="2026-09-07"
        )

        self.assertEqual("Sprint 1", current.resolved_title)
        self.assertEqual("Sprint 2", next_plan.resolved_title)
        self.assertEqual(
            ["Sprint 1"],
            [
                entry["title"]
                for entry in current.actions[0].payload["iteration_configuration"]["iterations"]
            ],
        )
        self.assertEqual(
            ["Sprint 1", "Sprint 2"],
            [
                entry["title"]
                for entry in next_plan.actions[0].payload["iteration_configuration"]["iterations"]
            ],
        )

    def test_empty_field_with_partial_schedule_fails_closed(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        partial = iteration_field(active=[], completed=[])
        partial["iteration_configuration"]["start_date"] = "2026-09-07"

        with self.assertRaisesRegex(ManifestError, "start.*no iterations"):
            build_iteration_plan(
                data, project_snapshot(partial), target="Sprint 1", as_of="2026-09-07"
            )

    def test_resolves_current_next_and_explicit_active_titles(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-08-03",
            "duration_days": 14,
        }
        snapshot = project_snapshot()

        current = build_iteration_plan(data, snapshot, target="@current", as_of="2026-08-27")
        next_plan = build_iteration_plan(data, snapshot, target="@next", as_of="2026-08-27")
        explicit = build_iteration_plan(data, snapshot, target="Sprint 11", as_of="2026-08-27")

        self.assertEqual(("Sprint 10", "ITER_10"), (current.resolved_title, current.resolved_iteration_id))
        self.assertEqual(("Sprint 11", "ITER_11"), (next_plan.resolved_title, next_plan.resolved_iteration_id))
        self.assertEqual("ITER_11", explicit.resolved_iteration_id)
        self.assertEqual([], current.actions)

    def test_rejects_completed_ambiguous_and_overlapping_targets(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-08-03",
            "duration_days": 14,
        }
        with self.assertRaisesRegex(ManifestError, "completed"):
            build_iteration_plan(
                data, project_snapshot(), target="Sprint 9", as_of="2026-08-27"
            )

        duplicate = iteration_field()
        duplicate["iteration_configuration"]["iterations"].append(
            {
                "id": "ITER_DUP",
                "title": "Sprint 11",
                "start_date": "2026-09-14",
                "duration_days": 14,
                "completed": False,
            }
        )
        with self.assertRaisesRegex(ManifestError, "duplicate title"):
            build_iteration_plan(
                data, project_snapshot(duplicate), target="Sprint 11", as_of="2026-08-27"
            )

        overlap = iteration_field()
        overlap["iteration_configuration"]["iterations"][1]["start_date"] = "2026-08-24"
        with self.assertRaisesRegex(ManifestError, "overlap"):
            build_iteration_plan(
                data, project_snapshot(overlap), target="@next", as_of="2026-08-27"
            )

    def test_missing_next_plans_full_replacement_and_converges_after_refresh(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-08-03",
            "duration_days": 14,
        }
        field = iteration_field(active=[iteration_field()["iteration_configuration"]["iterations"][0]])
        before = project_snapshot(field)

        plan = build_iteration_plan(data, before, target="@next", as_of="2026-08-27")

        self.assertEqual("Sprint 11", plan.resolved_title)
        self.assertIsNone(plan.resolved_iteration_id)
        self.assertEqual(["project.field.update_iterations"], [action.kind for action in plan.actions])
        update = plan.actions[0]
        self.assertEqual("FIELD_SPRINT", update.payload["field_id"])
        self.assertEqual(
            ["ITER_10", None],
            [entry.get("id") for entry in update.payload["iteration_configuration"]["iterations"]],
        )
        self.assertEqual(field, update.precondition["field"])

        after = project_snapshot(
            iteration_field(
                active=[
                    field["iteration_configuration"]["iterations"][0],
                    {
                        "id": "ITER_11",
                        "title": "Sprint 11",
                        "start_date": "2026-08-31",
                        "duration_days": 14,
                        "completed": False,
                    },
                ]
            )
        )
        converged = build_iteration_plan(data, after, target="@next", as_of="2026-08-27")
        self.assertEqual([], converged.actions)
        self.assertEqual("ITER_11", converged.resolved_iteration_id)
        self.assertEqual("ITER_11", verify_iteration_apply(plan, data, after).resolved_iteration_id)

        changed_identity = project_snapshot(
            iteration_field(
                active=[
                    {**after["fields"][0]["iteration_configuration"]["iterations"][0], "id": "REPLACED"},
                    after["fields"][0]["iteration_configuration"]["iterations"][1],
                ]
            )
        )
        with self.assertRaisesRegex(IterationAuthorizationError, "identity"):
            verify_iteration_apply(plan, data, changed_identity)

    def test_initialization_converges_only_after_server_assigns_target_identity(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-09-07",
            "duration_days": 14,
        }
        empty = iteration_field(active=[], completed=[])
        empty["iteration_configuration"]["start_date"] = None
        plan = build_iteration_plan(
            data, project_snapshot(empty), target="Sprint 1", as_of="2026-09-07"
        )
        after = iteration_field(
            active=[
                {
                    "id": "ITER_SERVER_1",
                    "title": "Sprint 1",
                    "start_date": "2026-09-07",
                    "duration_days": 14,
                    "completed": False,
                }
            ],
            completed=[],
        )
        after["iteration_configuration"]["start_date"] = "2026-09-07"

        verified = verify_iteration_apply(plan, data, project_snapshot(after))
        self.assertEqual("ITER_SERVER_1", verified.resolved_iteration_id)

        changed = iteration_field(
            active=[
                {
                    "id": "ITER_SERVER_1",
                    "title": "Sprint 1",
                    "start_date": "2026-09-08",
                    "duration_days": 14,
                    "completed": False,
                }
            ],
            completed=[],
        )
        changed["iteration_configuration"]["start_date"] = "2026-09-08"
        with self.assertRaisesRegex(IterationAuthorizationError, "identity"):
            verify_iteration_apply(plan, data, project_snapshot(changed))

    def test_rollover_derives_new_current_and_next_only_at_exact_boundary(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-08-03",
            "duration_days": 14,
        }
        completed = iteration_field()["iteration_configuration"]["completed_iterations"]
        field = iteration_field(active=[], completed=completed)

        plan = build_iteration_plan(
            data, project_snapshot(field), target="@current", as_of="2026-08-17"
        )

        entries = plan.actions[0].payload["iteration_configuration"]["iterations"]
        self.assertEqual(["Sprint 10", "Sprint 11"], [entry["title"] for entry in entries])
        self.assertEqual("Sprint 10", plan.resolved_title)

    def test_unsafe_title_or_schedule_extension_fails_closed(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-08-03",
            "duration_days": 14,
        }
        unnamed = iteration_field(active=[{
            "id": "ITER_X",
            "title": "Launch",
            "start_date": "2026-08-17",
            "duration_days": 14,
            "completed": False,
        }])
        with self.assertRaisesRegex(ManifestError, "derive.*title"):
            build_iteration_plan(
                data, project_snapshot(unnamed), target="@next", as_of="2026-08-27"
            )

        mismatched = iteration_field(duration=7)
        with self.assertRaisesRegex(ManifestError, "duration"):
            build_iteration_plan(
                data, project_snapshot(mismatched), target="@next", as_of="2026-08-27"
            )

    def test_apply_binds_fresh_state_and_journals_partial_failure(self) -> None:
        data = manifest()
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-08-03",
            "duration_days": 14,
        }
        field = iteration_field(active=[iteration_field()["iteration_configuration"]["iterations"][0]])
        snapshot = project_snapshot(field)
        plan = build_iteration_plan(data, snapshot, target="@next", as_of="2026-08-27")
        journal = []

        with self.assertRaisesRegex(IterationAuthorizationError, "drift"):
            apply_iteration_plan(
                plan,
                executor=lambda action: None,
                confirmation=plan.digest,
                manifest=data,
                project_snapshot=project_snapshot(),
            )

        with self.assertRaisesRegex(RuntimeError, "injected"):
            apply_iteration_plan(
                plan,
                executor=lambda action: (_ for _ in ()).throw(RuntimeError("injected")),
                confirmation=plan.digest,
                manifest=data,
                project_snapshot=snapshot,
                journal=journal.append,
            )
        self.assertEqual("failed", journal[-1].status)
        self.assertEqual(plan.actions[0].as_dict(), journal[-1].failed_action)


if __name__ == "__main__":
    unittest.main()
