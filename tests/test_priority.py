from __future__ import annotations

import unittest

from agentic_backlog_kit.priority import explain_next, prioritize, select_next

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



class ExplainNextTests(unittest.TestCase):
    """R26 - a selection nobody can audit cannot be picked up."""

    def test_reports_the_higher_ranked_item_it_passed_over(self) -> None:
        data = manifest(
            item("T-BLOCKER", impact=5, business_value=5, maturity="idea"),
            item("T-READY", impact=1, business_value=1),
        )

        selected, passed_over = explain_next(data)

        self.assertEqual("T-READY", selected.id)
        self.assertEqual(["T-BLOCKER"], [entry["id"] for entry in passed_over])
        self.assertIn("not refined", passed_over[0]["reason"])

    def test_names_the_dependency_that_is_in_the_way(self) -> None:
        data = manifest(
            item("T-FIRST", impact=1, business_value=1, maturity="idea"),
            item("T-SECOND", impact=5, business_value=5, depends_on=["T-FIRST"]),
            item("T-READY", impact=1, business_value=1),
        )

        _, passed_over = explain_next(data)

        reasons = {entry["id"]: entry["reason"] for entry in passed_over}
        self.assertIn("waiting on T-FIRST", reasons["T-SECOND"])

    def test_a_container_is_named_as_a_container(self) -> None:
        data = manifest(
            item("F-1", item_type="Feature", impact=5, business_value=5),
            item("S-1", item_type="Story", parent="F-1", impact=1, business_value=1),
        )

        _, passed_over = explain_next(data)

        self.assertIn("container", passed_over[0]["reason"])

    def test_completed_work_is_not_reported_as_an_obstacle(self) -> None:
        data = manifest(
            item("T-DONE", status="Done", impact=5, business_value=5),
            item("T-READY", impact=1, business_value=1),
        )

        _, passed_over = explain_next(data)

        self.assertNotIn("T-DONE", [entry["id"] for entry in passed_over])

    def test_nothing_executable_still_explains_the_whole_head(self) -> None:
        data = manifest(item("T-1", maturity="idea"), item("T-2", status="Blocked"))

        selected, passed_over = explain_next(data)

        self.assertIsNone(selected)
        self.assertEqual({"T-1", "T-2"}, {entry["id"] for entry in passed_over})

    def test_the_explanation_can_be_turned_off(self) -> None:
        data = manifest(item("T-BLOCKED", maturity="idea"), item("T-READY"))

        selected, passed_over = explain_next(data, limit=0)

        self.assertEqual("T-READY", selected.id)
        self.assertEqual([], passed_over)

    def test_select_next_still_answers_the_same_item(self) -> None:
        data = manifest(item("T-BLOCKED", maturity="idea"), item("T-READY"))

        self.assertEqual(select_next(data).id, explain_next(data)[0].id)
