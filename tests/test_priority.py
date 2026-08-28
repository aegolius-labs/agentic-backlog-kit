from __future__ import annotations

import unittest

from agentic_backlog_kit.priority import prioritize, select_next

from tests.helpers import item, manifest


class PriorityTests(unittest.TestCase):
    def test_uses_all_five_priority_dimensions(self) -> None:
        data = manifest(
            item(
                "T-1",
                impact=4,
                effort=2,
                business_value=5,
                enabler_value=3,
            )
        )

        scored = prioritize(data)

        # impact*2 + business*2 + enabler + (6-effort)
        self.assertEqual(25.0, scored[0].base_score)
        self.assertEqual(25.0, scored[0].priority_score)

    def test_boosts_a_prerequisite_but_keeps_dependency_order(self) -> None:
        data = manifest(
            item(
                "T-BASE",
                impact=1,
                effort=1,
                business_value=1,
                enabler_value=0,
            ),
            item(
                "T-VALUE",
                depends_on=["T-BASE"],
                impact=5,
                effort=2,
                business_value=5,
                enabler_value=0,
            ),
        )

        scored = prioritize(data)

        self.assertEqual(["T-BASE", "T-VALUE"], [entry.id for entry in scored])
        self.assertEqual(15.0, scored[0].priority_score)
        self.assertEqual(24.0, scored[1].priority_score)

    def test_done_items_are_zero_and_not_selected(self) -> None:
        data = manifest(
            item("T-DONE", status="Done", impact=5, business_value=5),
            item("T-NEXT", impact=1, business_value=1),
        )

        scored = {entry.id: entry for entry in prioritize(data)}
        next_item = select_next(data)

        self.assertEqual(0.0, scored["T-DONE"].priority_score)
        self.assertEqual("T-NEXT", next_item.id)

    def test_blocked_and_unrefined_items_are_not_selected(self) -> None:
        data = manifest(
            item("T-BLOCKED", status="Blocked", impact=5, business_value=5),
            item("T-IDEA", maturity="idea", impact=5, business_value=5),
            item("T-NEXT", impact=2, business_value=2),
        )

        self.assertEqual("T-NEXT", select_next(data).id)

    def test_ties_are_stable_by_item_id(self) -> None:
        data = manifest(item("T-B"), item("T-A"))

        self.assertEqual(["T-A", "T-B"], [entry.id for entry in prioritize(data)])


if __name__ == "__main__":
    unittest.main()

