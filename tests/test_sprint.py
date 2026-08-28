from __future__ import annotations

import unittest

from agentic_backlog_kit.manifest import ManifestError
from agentic_backlog_kit.sprint import plan_sprint

from tests.helpers import item, manifest


class SprintPlanningTests(unittest.TestCase):
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

        plan = plan_sprint(data, capacity=5, sprint="Sprint 1")

        self.assertEqual(["T-BASE", "T-VALUE"], [entry.id for entry in plan.items])
        self.assertEqual(5, plan.committed_effort)
        self.assertEqual(0, plan.remaining_capacity)

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


if __name__ == "__main__":
    unittest.main()
