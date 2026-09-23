from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path

from agentic_backlog_kit.manifest import ManifestError
from agentic_backlog_kit.schedule import (
    build_schedule,
    render_markdown,
    render_mermaid,
)

from tests.helpers import item, manifest


START = "2026-01-05"


def _manifest(*items: dict) -> dict:
    data = manifest(*items)
    data["workflow"]["iteration"] = {
        "field": "Sprint",
        "start_date": START,
        "duration_days": 14,
    }
    return data


class ScheduleTests(unittest.TestCase):
    """R27 - a projection the dependency graph and the effort points imply."""

    def test_duration_comes_from_effort_and_the_declared_factor(self) -> None:
        schedule = build_schedule(_manifest(item("T-1", effort=3)), days_per_effort=2)

        placed = schedule.items[0]
        self.assertEqual(6, placed.duration_days)
        self.assertEqual(date(2026, 1, 5), placed.start)
        self.assertEqual(date(2026, 1, 10), placed.end)

    def test_a_dependency_starts_its_dependent_the_day_after_it_ends(self) -> None:
        schedule = build_schedule(
            _manifest(item("T-1", effort=1), item("T-2", effort=1, depends_on=["T-1"])),
            days_per_effort=1,
        )

        by_id = {entry.id: entry for entry in schedule.items}
        self.assertEqual(date(2026, 1, 5), by_id["T-1"].start)
        self.assertEqual(date(2026, 1, 6), by_id["T-2"].start)

    def test_one_lane_serializes_independent_work(self) -> None:
        schedule = build_schedule(
            _manifest(item("T-1", effort=1), item("T-2", effort=1)),
            days_per_effort=1,
            lanes=1,
        )

        starts = {entry.id: entry.start for entry in schedule.items}
        self.assertNotEqual(starts["T-1"], starts["T-2"])

    def test_two_lanes_run_independent_work_together(self) -> None:
        schedule = build_schedule(
            _manifest(item("T-1", effort=1), item("T-2", effort=1)),
            days_per_effort=1,
            lanes=2,
        )

        starts = {entry.id: entry.start for entry in schedule.items}
        self.assertEqual(starts["T-1"], starts["T-2"])

    def test_lanes_never_reorder_a_dependency(self) -> None:
        schedule = build_schedule(
            _manifest(item("T-1", effort=2), item("T-2", effort=1, depends_on=["T-1"])),
            days_per_effort=1,
            lanes=4,
        )

        by_id = {entry.id: entry for entry in schedule.items}
        self.assertGreater(by_id["T-2"].start, by_id["T-1"].end)

    def test_completed_work_is_excluded_with_its_reason(self) -> None:
        schedule = build_schedule(
            _manifest(item("T-1", status="Done"), item("T-2"))
        )

        self.assertEqual(["T-2"], [entry.id for entry in schedule.items])
        self.assertIn("already complete", schedule.excluded["T-1"])

    def test_completed_work_can_be_drawn_when_asked(self) -> None:
        schedule = build_schedule(
            _manifest(item("T-1", status="Done"), item("T-2")),
            include_completed=True,
        )

        by_id = {entry.id: entry for entry in schedule.items}
        self.assertEqual("done", by_id["T-1"].state)

    def test_a_container_is_excluded_because_its_children_carry_the_work(self) -> None:
        schedule = build_schedule(
            _manifest(
                item("F-1", item_type="Feature"),
                item("S-1", item_type="Story", parent="F-1"),
            )
        )

        self.assertEqual(["S-1"], [entry.id for entry in schedule.items])
        self.assertIn("children carry", schedule.excluded["F-1"])

    def test_a_container_with_no_children_is_the_work(self) -> None:
        """An undecomposed feature is the largest thing left, not a grouping."""

        schedule = build_schedule(
            _manifest(
                item("F-DECOMPOSED", item_type="Feature"),
                item("S-1", item_type="Story", parent="F-DECOMPOSED"),
                item("F-WHOLE", item_type="Feature"),
            )
        )

        self.assertIn("F-WHOLE", [entry.id for entry in schedule.items])
        self.assertNotIn("F-WHOLE", schedule.excluded)

    def test_the_critical_path_is_the_longest_scheduled_chain(self) -> None:
        schedule = build_schedule(
            _manifest(
                item("T-1", effort=1),
                item("T-2", effort=5, depends_on=["T-1"]),
                item("T-3", effort=1, depends_on=["T-2"]),
                item("T-4", effort=1),
            ),
            days_per_effort=1,
            lanes=4,
        )

        self.assertEqual(["T-1", "T-2", "T-3"], schedule.critical_path)

    def test_an_item_is_grouped_under_its_immediate_parent(self) -> None:
        schedule = build_schedule(
            _manifest(
                item("E-1", item_type="Epic", title="Delivery"),
                item("F-1", item_type="Feature", title="Checkout", parent="E-1"),
                item("S-1", item_type="Story", parent="F-1"),
            )
        )

        self.assertEqual("Checkout", schedule.items[0].section)

    def test_an_unparented_item_says_so(self) -> None:
        schedule = build_schedule(_manifest(item("T-1")))

        self.assertEqual("Unparented", schedule.items[0].section)

    def test_the_projection_is_deterministic(self) -> None:
        data = _manifest(
            item("T-1", effort=2), item("T-2", effort=3), item("T-3", depends_on=["T-1"])
        )

        first = build_schedule(data, lanes=2).as_dict()
        second = build_schedule(data, lanes=2).as_dict()

        self.assertEqual(first, second)

    def test_an_explicit_start_overrides_the_iteration(self) -> None:
        schedule = build_schedule(_manifest(item("T-1")), start="2026-03-02")

        self.assertEqual(date(2026, 3, 2), schedule.start)

    def test_refuses_a_backlog_with_no_start_date_to_project_from(self) -> None:
        with self.assertRaisesRegex(ManifestError, "start date"):
            build_schedule(manifest(item("T-1")))

    def test_refuses_a_malformed_start(self) -> None:
        with self.assertRaisesRegex(ManifestError, "ISO date"):
            build_schedule(_manifest(item("T-1")), start="March")

    def test_refuses_a_non_positive_lane_count_or_factor(self) -> None:
        with self.assertRaisesRegex(ManifestError, "lanes"):
            build_schedule(_manifest(item("T-1")), lanes=0)
        with self.assertRaisesRegex(ManifestError, "days_per_effort"):
            build_schedule(_manifest(item("T-1")), days_per_effort=0)


class RenderTests(unittest.TestCase):
    def test_mermaid_names_each_section_once(self) -> None:
        schedule = build_schedule(
            _manifest(
                item("F-1", item_type="Feature", title="Checkout", parent=None),
                item("S-1", item_type="Story", parent="F-1", effort=1),
                item("S-2", item_type="Story", parent="F-1", effort=1),
            ),
            days_per_effort=1,
        )

        rendered = render_mermaid(schedule)

        self.assertEqual(1, rendered.count("section Checkout"))
        self.assertTrue(rendered.startswith("```mermaid\ngantt"))

    def test_mermaid_keeps_a_colon_out_of_a_label(self) -> None:
        schedule = build_schedule(_manifest(item("T-1", title="Fix: the thing")))

        line = [
            entry
            for entry in render_mermaid(schedule).splitlines()
            if "T-1" in entry
        ][0]

        self.assertEqual(1, line.count(":"))

    def test_markdown_states_its_basis_and_its_limits(self) -> None:
        schedule = build_schedule(
            _manifest(item("T-1", status="Done"), item("T-2")), lanes=3
        )

        rendered = render_markdown(schedule, command="abk gantt")

        self.assertIn("projection, not an estimate", rendered)
        self.assertIn("Parallel lanes: 3", rendered)
        self.assertIn("Regenerate with `abk gantt`", rendered)
        self.assertIn("## Not scheduled", rendered)
        self.assertIn("`T-1`", rendered)




class GeneratedProjectionTests(unittest.TestCase):
    """The committed projection must still describe the committed backlog.

    A generated artifact nobody regenerates is worse than none, because it
    reads as current. This fails the moment the manifest moves without the
    chart moving with it.
    """

    ROOT = Path(__file__).resolve().parents[1]
    CHART = ROOT / "docs" / "roadmap-gantt.md"
    COMMAND = "abk gantt --lanes 1 --days-per-effort 2"
    TITLE = "Agentic Backlog Kit roadmap projection"

    def test_the_committed_chart_matches_the_committed_manifest(self) -> None:
        source = json.loads(
            (self.ROOT / ".agentic-backlog" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )

        expected = render_markdown(
            build_schedule(source, days_per_effort=2, lanes=1),
            title=self.TITLE,
            command=self.COMMAND,
        )

        self.assertEqual(
            expected,
            self.CHART.read_text(encoding="utf-8"),
            "docs/roadmap-gantt.md is stale; regenerate it with "
            f"`python scripts/backlog.py gantt --lanes 1 --days-per-effort 2 "
            f'--title "{self.TITLE}" --output docs/roadmap-gantt.md`',
        )
if __name__ == "__main__":
    unittest.main()
