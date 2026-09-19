from __future__ import annotations

import unittest

from agentic_backlog_kit.manifest import ManifestError
from agentic_backlog_kit.sprint import plan_sprint, sprint_plan_payload

from tests.helpers import item, manifest


TARGET = "Sprint 1"
ITERATION = {"field": "Sprint", "start_date": "2026-09-21", "duration_days": 14}
SNAPSHOT = {
    "fields": [
        {
            "id": "FIELD_SPRINT",
            "database_id": 42,
            "name": "Sprint",
            "data_type": "ITERATION",
            "iteration_configuration": {
                "start_date": "2026-09-07",
                "duration_days": 14,
                "iterations": [
                    {
                        "id": "ITER_1",
                        "title": TARGET,
                        "start_date": "2026-09-21",
                        "duration_days": 14,
                        "completed": False,
                    }
                ],
                "completed_iterations": [],
            },
        }
    ],
    "views": [],
    "labels": [],
}


def _manifest(*items: dict) -> dict:
    data = manifest(*items)
    data["workflow"]["iteration"] = dict(ITERATION)
    return data


def _plan(data: dict, **kwargs):
    kwargs.setdefault("sprint", TARGET)
    return plan_sprint(
        data, project_snapshot=SNAPSHOT, as_of="2026-09-21", **kwargs
    )


class RetainedCommitmentTests(unittest.TestCase):
    """R16/policy A - work already in the sprint is counted once, not re-selected."""

    def test_retains_work_already_committed_to_the_target(self) -> None:
        data = _manifest(
            item("A", sprint=TARGET, effort=3),
            item("B", effort=2),
        )

        plan = _plan(data, capacity=8)

        self.assertEqual(["A"], [entry.id for entry in plan.retained])
        self.assertEqual(3, plan.retained_effort)
        self.assertNotIn("A", [entry.id for entry in plan.items])

    def test_retained_effort_is_counted_exactly_once(self) -> None:
        data = _manifest(
            item("A", sprint=TARGET, effort=3),
            item("B", effort=2),
        )

        plan = _plan(data, capacity=8)

        self.assertEqual(5, plan.committed_effort)
        self.assertEqual(3, plan.remaining_capacity)

    def test_preserves_an_ongoing_status_rather_than_dropping_the_item(self) -> None:
        data = _manifest(item("A", status="In Progress", sprint=TARGET, effort=3))

        plan = _plan(data, capacity=8)

        retained = plan.retained[0]
        self.assertEqual("A", retained.id)
        self.assertEqual("In Progress", retained.status)

    def test_a_blocked_item_already_in_the_sprint_still_occupies_it(self) -> None:
        data = _manifest(item("A", status="Blocked", sprint=TARGET, effort=4))

        plan = _plan(data, capacity=8)

        self.assertEqual(["A"], [entry.id for entry in plan.retained])
        self.assertEqual(4, plan.retained_effort)

    def test_completed_work_in_the_sprint_is_not_retained(self) -> None:
        data = _manifest(item("A", status="Done", sprint=TARGET, effort=4))

        plan = _plan(data, capacity=8)

        self.assertEqual([], plan.retained)
        self.assertEqual(0, plan.retained_effort)

    def test_reports_overage_when_commitments_exceed_capacity(self) -> None:
        data = _manifest(
            item("X", sprint=TARGET, effort=5),
            item("Y", sprint=TARGET, effort=5),
            item("Z", effort=1),
        )

        plan = _plan(data, capacity=6)

        self.assertEqual(10, plan.retained_effort)
        self.assertEqual(4, plan.overage)
        self.assertEqual([], [entry.id for entry in plan.items])

    def test_replanning_is_stable(self) -> None:
        data = _manifest(
            item("A", status="In Progress", sprint=TARGET, effort=3),
            item("B", effort=2),
            item("C", effort=2),
        )

        first = _plan(data, capacity=8)
        second = _plan(data, capacity=8)

        self.assertEqual(
            [entry.id for entry in first.items], [entry.id for entry in second.items]
        )
        self.assertEqual(
            [entry.id for entry in first.retained],
            [entry.id for entry in second.retained],
        )


class CarryoverTests(unittest.TestCase):
    """R16/policy A - work committed elsewhere never moves on its own."""

    def test_work_committed_elsewhere_is_withheld_even_when_it_ranks_first(self) -> None:
        data = _manifest(
            item("B", sprint="Sprint 2", effort=2, impact=5, business_value=5),
            item("C", effort=2, impact=1, business_value=1),
        )

        plan = _plan(data, capacity=8)

        self.assertNotIn("B", [entry.id for entry in plan.items])
        self.assertEqual({"B": "Sprint 2"}, plan.carryover_available)

    def test_an_explicit_carryover_moves_the_item(self) -> None:
        data = _manifest(
            item("B", sprint="Sprint 2", effort=2, impact=5, business_value=5),
            item("C", effort=2),
        )

        plan = _plan(data, capacity=8, carryover={"B"})

        self.assertIn("B", [entry.id for entry in plan.items])
        self.assertEqual(["B"], plan.carryover_selected)
        self.assertEqual({}, plan.carryover_available)

    def test_carryover_is_reported_once_and_not_repeated_in_skipped(self) -> None:
        data = _manifest(item("B", sprint="Sprint 2", effort=2))

        plan = _plan(data, capacity=8)

        self.assertIn("B", plan.carryover_available)
        self.assertNotIn("B", plan.skipped)

    def test_rejects_an_unknown_carryover_item(self) -> None:
        data = _manifest(item("B", sprint="Sprint 2"))

        with self.assertRaisesRegex(ManifestError, "unknown item"):
            _plan(data, capacity=8, carryover={"T-404"})

    def test_rejects_carrying_over_work_already_in_the_target(self) -> None:
        data = _manifest(item("A", sprint=TARGET))

        with self.assertRaisesRegex(ManifestError, "already committed"):
            _plan(data, capacity=8, carryover={"A"})

    def test_rejects_carrying_over_unassigned_work(self) -> None:
        data = _manifest(item("C"))

        with self.assertRaisesRegex(ManifestError, "not committed to a sprint"):
            _plan(data, capacity=8, carryover={"C"})

    def test_rejects_carrying_over_completed_work(self) -> None:
        data = _manifest(item("B", sprint="Sprint 2", status="Done"))

        with self.assertRaisesRegex(ManifestError, "already complete"):
            _plan(data, capacity=8, carryover={"B"})

    def test_rejects_carryover_without_a_target_sprint(self) -> None:
        data = _manifest(item("B", sprint="Sprint 2"))

        with self.assertRaisesRegex(ManifestError, "requires a target sprint"):
            plan_sprint(data, capacity=8, carryover={"B"})


class UntargetedPlanningTests(unittest.TestCase):
    """Without a target there is no commitment boundary to protect."""

    def test_an_untargeted_plan_ignores_sprint_assignment(self) -> None:
        data = _manifest(
            item("B", sprint="Sprint 2", effort=2, impact=5, business_value=5),
            item("C", effort=2),
        )

        plan = plan_sprint(data, capacity=8)

        self.assertIn("B", [entry.id for entry in plan.items])
        self.assertEqual({}, plan.carryover_available)
        self.assertEqual([], plan.retained)


class ProjectionTests(unittest.TestCase):
    """Every list that grows with the backlog must be boundable."""

    def test_the_limit_projects_retained_and_carryover_too(self) -> None:
        items = [item(f"R-{index:03d}", sprint=TARGET, effort=1) for index in range(30)]
        items += [
            item(f"E-{index:03d}", sprint="Sprint 2", effort=1) for index in range(30)
        ]
        plan = _plan(_manifest(*items), capacity=50)

        payload = sprint_plan_payload(plan, skipped_limit=5)

        self.assertEqual(5, len(payload["retained"]))
        self.assertEqual(30, payload["retained_count"])
        self.assertTrue(payload["retained_truncated"])
        self.assertEqual(5, len(payload["carryover_available"]))
        self.assertEqual(30, payload["carryover_available_count"])
        self.assertTrue(payload["carryover_available_truncated"])

    def test_retained_entries_stay_compact(self) -> None:
        data = _manifest(item("A", sprint=TARGET, effort=3))

        payload = sprint_plan_payload(_plan(data, capacity=8))

        self.assertEqual(
            {"id", "title", "type", "status", "effort"}, set(payload["retained"][0])
        )


if __name__ == "__main__":
    unittest.main()
