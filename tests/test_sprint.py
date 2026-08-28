from __future__ import annotations

import unittest

from agentic_backlog_kit.manifest import ManifestError
from agentic_backlog_kit.sprint import plan_sprint, sprint_plan_payload

from tests.helpers import item, manifest


class SprintPlanningTests(unittest.TestCase):
    @staticmethod
    def _iteration_snapshot() -> dict:
        return {
            "fields": [
                {
                    "id": "FIELD_SPRINT",
                    "name": "Sprint",
                    "data_type": "ITERATION",
                    "iteration_configuration": {
                        "start_date": "2026-08-03",
                        "duration_days": 14,
                        "iterations": [
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
                        "completed_iterations": [],
                    },
                }
            ]
        }

    def test_selects_dependencies_before_dependents_within_capacity(self) -> None:
        data = manifest(
            item("T-BASE", effort=2, impact=1, business_value=1),
            item(
                "T-VALUE",
                effort=3,
                impact=5,
                business_value=5,
                depends_on=["T-BASE"],
            ),
            item("T-LOW", effort=2, impact=1, business_value=1),
        )

        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-08-03",
            "duration_days": 14,
        }
        plan = plan_sprint(
            data,
            capacity=5,
            sprint="@next",
            project_snapshot=self._iteration_snapshot(),
            as_of="2026-08-27",
        )

        self.assertEqual(["T-BASE", "T-VALUE"], [entry.id for entry in plan.items])
        self.assertEqual(5, plan.committed_effort)
        self.assertEqual(0, plan.remaining_capacity)
        self.assertEqual("Sprint 11", plan.sprint)
        self.assertEqual("ITER_11", plan.iteration_id)
        self.assertTrue(plan.ready_to_commit)

    def test_target_requires_project_state_and_rejects_completed_iteration(self) -> None:
        data = manifest(item("T-1"))
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "2026-08-03",
            "duration_days": 14,
        }

        with self.assertRaisesRegex(ManifestError, "snapshot"):
            plan_sprint(data, sprint="Sprint 10", as_of="2026-08-27")

        snapshot = self._iteration_snapshot()
        snapshot["fields"][0]["iteration_configuration"]["completed_iterations"] = [
            {
                "id": "ITER_9",
                "title": "Sprint 9",
                "start_date": "2026-08-03",
                "duration_days": 14,
                "completed": True,
            }
        ]
        with self.assertRaisesRegex(ManifestError, "completed"):
            plan_sprint(
                data,
                sprint="Sprint 9",
                project_snapshot=snapshot,
                as_of="2026-08-27",
            )

    def test_tracking_layers_do_not_consume_sprint_capacity(self) -> None:
        data = manifest(
            item("F-1", item_type="Feature", effort=1, impact=5, business_value=5),
            item("T-1", item_type="Task", effort=3),
        )

        plan = plan_sprint(data, capacity=4)

        self.assertEqual(["T-1"], [entry.id for entry in plan.items])
        self.assertEqual(3, plan.committed_effort)

    def test_does_not_select_a_dependent_when_prerequisite_cannot_fit(self) -> None:
        data = manifest(
            item("T-BASE", effort=5, impact=1, business_value=1),
            item(
                "T-VALUE",
                effort=1,
                impact=5,
                business_value=5,
                depends_on=["T-BASE"],
            ),
        )

        plan = plan_sprint(data, capacity=3)

        self.assertEqual([], plan.items)
        self.assertIn("T-BASE", plan.skipped)
        self.assertIn("T-VALUE", plan.skipped)

    def test_explicit_zero_capacity_is_rejected(self) -> None:
        with self.assertRaisesRegex(ManifestError, "positive integer"):
            plan_sprint(manifest(item("T-1")), capacity=0)

    def test_skipped_limit_projects_large_preview_with_total(self) -> None:
        data = manifest(
            item("T-1", effort=1),
            item("T-2", effort=5),
            item("T-3", effort=5),
            item("T-4", effort=5),
        )

        plan = plan_sprint(data, capacity=1)
        payload = sprint_plan_payload(plan, skipped_limit=2)

        self.assertEqual(3, payload["skipped_count"])
        self.assertEqual(2, len(payload["skipped"]))
        self.assertTrue(payload["skipped_truncated"])

    def test_negative_skipped_limit_is_rejected(self) -> None:
        with self.assertRaisesRegex(ManifestError, "skipped_limit"):
            sprint_plan_payload(plan_sprint(manifest(item("T-1"))), skipped_limit=-1)


if __name__ == "__main__":
    unittest.main()
