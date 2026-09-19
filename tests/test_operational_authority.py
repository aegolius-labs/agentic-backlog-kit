from __future__ import annotations

import unittest

from agentic_backlog_kit.manifest import ManifestError
from agentic_backlog_kit.priority import prioritize
from agentic_backlog_kit.sync import (
    build_sync_plan,
    compose_operational_state,
)

from tests.helpers import item, manifest


SPRINT_FIELD = {"field": "Sprint", "start_date": "2026-09-21", "duration_days": 14}


def _manifest(*items: dict) -> dict:
    data = manifest(*items)
    data["workflow"]["iteration"] = dict(SPRINT_FIELD)
    return data


def _remote(
    item_id: str = "T-1",
    *,
    status: str = "In Progress",
    sprint: str | None = None,
    in_project: bool = True,
    number: int = 7,
) -> dict:
    fields: dict = {
        "Status": status,
        "Impact": 3,
        "Effort": 3,
        "Business Value": 3,
        "Enabler Value": 0,
        "Priority": 15.0,
    }
    if sprint is not None:
        fields["Sprint"] = sprint
    return {
        "abk_id": item_id,
        "number": number,
        "title": item_id,
        "body": "",
        "type": "Task",
        "labels": [],
        "in_project": in_project,
        "project_fields": fields,
    }


def _snapshot(*issues: dict) -> dict:
    return {"issues": list(issues)}


class OrdinarySyncAuthorityTests(unittest.TestCase):
    """R15/D1 - GitHub owns Status and Sprint for work it already tracks."""

    def test_ordinary_sync_does_not_rewrite_remote_status(self) -> None:
        data = _manifest(item("T-1", status="Ready"))

        plan = build_sync_plan(data, _snapshot(_remote(status="In Progress")),
                               manage_body=False)

        written = [
            name
            for action in plan.actions
            for name in action.payload.get("fields", {})
        ]
        self.assertNotIn("Status", written)

    def test_ordinary_sync_does_not_rewrite_remote_sprint(self) -> None:
        data = _manifest(item("T-1", status="Ready", sprint="Sprint 1"))

        plan = build_sync_plan(
            data,
            _snapshot(_remote(status="Ready", sprint="Sprint 4")),
            manage_body=False,
        )

        written = [
            name
            for action in plan.actions
            for name in action.payload.get("fields", {})
        ]
        self.assertNotIn("Sprint", written)

    def test_planning_fields_are_still_reconciled(self) -> None:
        data = _manifest(item("T-1", status="Ready", impact=5))

        plan = build_sync_plan(data, _snapshot(_remote()), manage_body=False)

        fields = {
            name: value
            for action in plan.actions
            for name, value in action.payload.get("fields", {}).items()
        }
        self.assertEqual(5, fields["Impact"])

    def test_a_new_item_still_receives_manifest_defaults(self) -> None:
        data = _manifest(item("T-1", status="Ready"))

        plan = build_sync_plan(data, _snapshot(), manage_body=False)

        add = [a for a in plan.actions if a.kind == "project.add_item"][0]
        self.assertEqual("Ready", add.payload["fields"]["Status"])

    def test_an_item_not_yet_in_the_project_receives_manifest_defaults(self) -> None:
        data = _manifest(item("T-1", status="Ready"))

        plan = build_sync_plan(
            data, _snapshot(_remote(in_project=False)), manage_body=False
        )

        add = [a for a in plan.actions if a.kind == "project.add_item"][0]
        self.assertEqual("Ready", add.payload["fields"]["Status"])


class ExplicitTransitionTests(unittest.TestCase):
    """R15 - local intent moves operational state only through a reviewed transition."""

    def test_transition_emits_a_bound_action_carrying_the_observed_value(self) -> None:
        data = _manifest(item("T-1", status="Ready"))

        plan = build_sync_plan(
            data,
            _snapshot(_remote(status="In Progress")),
            manage_body=False,
            transitions={"T-1": {"Status": "Done"}},
        )

        transition = [a for a in plan.actions if a.kind == "project.transition"][0]
        self.assertEqual({"Status": "Done"}, transition.payload["fields"])
        self.assertEqual({"Status": "In Progress"}, transition.precondition["observed"])

    def test_transition_matching_remote_state_plans_nothing(self) -> None:
        data = _manifest(item("T-1", status="Ready"))

        plan = build_sync_plan(
            data,
            _snapshot(_remote(status="In Progress")),
            manage_body=False,
            transitions={"T-1": {"Status": "In Progress"}},
        )

        self.assertEqual(
            [], [a for a in plan.actions if a.kind == "project.transition"]
        )

    def test_transitions_change_the_plan_digest(self) -> None:
        data = _manifest(item("T-1", status="Ready"))
        snapshot = _snapshot(_remote(status="In Progress"))

        plain = build_sync_plan(data, snapshot, manage_body=False)
        moved = build_sync_plan(
            data, snapshot, manage_body=False,
            transitions={"T-1": {"Status": "Done"}},
        )

        self.assertNotEqual(plain.digest, moved.digest)

    def test_transition_survives_a_plan_round_trip(self) -> None:
        from agentic_backlog_kit.sync import sync_plan_from_dict

        data = _manifest(item("T-1", status="Ready"))
        plan = build_sync_plan(
            data,
            _snapshot(_remote(status="In Progress")),
            manage_body=False,
            transitions={"T-1": {"Status": "Done"}},
        )

        restored = sync_plan_from_dict(plan.as_dict())

        self.assertEqual(plan.digest, restored.digest)
        self.assertEqual({"T-1": {"Status": "Done"}}, restored.transitions)

    def test_rejects_a_transition_for_an_unknown_item(self) -> None:
        data = _manifest(item("T-1"))

        with self.assertRaisesRegex(ManifestError, "unknown item"):
            build_sync_plan(
                data, _snapshot(_remote()), transitions={"T-404": {"Status": "Done"}}
            )

    def test_rejects_a_status_outside_the_manifest_workflow(self) -> None:
        data = _manifest(item("T-1"))

        with self.assertRaisesRegex(ManifestError, "not one of the manifest"):
            build_sync_plan(
                data, _snapshot(_remote()), transitions={"T-1": {"Status": "Shipped"}}
            )

    def test_rejects_a_non_operational_field(self) -> None:
        data = _manifest(item("T-1"))

        with self.assertRaisesRegex(ManifestError, "may only set"):
            build_sync_plan(
                data, _snapshot(_remote()), transitions={"T-1": {"Impact": 5}}
            )

    def test_rejects_an_unresolved_sprint_alias(self) -> None:
        data = _manifest(item("T-1"))

        with self.assertRaisesRegex(ManifestError, "alias must be resolved"):
            build_sync_plan(
                data, _snapshot(_remote()), transitions={"T-1": {"Sprint": "@current"}}
            )

    def test_rejects_a_transition_for_work_github_does_not_track(self) -> None:
        data = _manifest(item("T-1"))

        with self.assertRaisesRegex(ManifestError, "existing GitHub issue"):
            build_sync_plan(
                data, _snapshot(), transitions={"T-1": {"Status": "Done"}}
            )

    def test_rejects_a_transition_for_an_item_outside_the_project(self) -> None:
        data = _manifest(item("T-1"))

        with self.assertRaisesRegex(ManifestError, "in the Project"):
            build_sync_plan(
                data,
                _snapshot(_remote(in_project=False)),
                transitions={"T-1": {"Status": "Done"}},
            )


class ComposedOperationalStateTests(unittest.TestCase):
    """R15 - planning reads what is happening now from GitHub."""

    def test_adopts_a_remote_status_the_manifest_defines(self) -> None:
        data = _manifest(item("T-1", status="Ready"))

        composed, differences = compose_operational_state(
            data, _snapshot(_remote(status="Done"))
        )

        self.assertEqual("Done", composed["items"][0]["status"])
        self.assertTrue(differences[0]["applied"])

    def test_reports_but_does_not_adopt_an_unmapped_remote_status(self) -> None:
        data = _manifest(item("T-1", status="Ready"))

        composed, differences = compose_operational_state(
            data, _snapshot(_remote(status="Todo"))
        )

        self.assertEqual("Ready", composed["items"][0]["status"])
        self.assertFalse(differences[0]["applied"])

    def test_adopts_a_remote_sprint(self) -> None:
        data = _manifest(item("T-1", sprint=None))

        composed, _ = compose_operational_state(
            data, _snapshot(_remote(sprint="Sprint 3"))
        )

        self.assertEqual("Sprint 3", composed["items"][0]["sprint"])

    def test_ignores_work_github_does_not_track(self) -> None:
        data = _manifest(item("T-1", status="Ready"))

        composed, differences = compose_operational_state(data, _snapshot())

        self.assertEqual("Ready", composed["items"][0]["status"])
        self.assertEqual([], differences)

    def test_a_remotely_completed_prerequisite_stops_boosting(self) -> None:
        data = _manifest(
            item("A", status="Ready"),
            item("B", depends_on=["A"], status="Ready", impact=5, business_value=5),
        )
        stale = {entry.id: entry.priority_score for entry in prioritize(data)}

        composed, _ = compose_operational_state(
            data, _snapshot(_remote("B", status="Done", number=8))
        )
        fresh = {entry.id: entry.priority_score for entry in prioritize(composed)}

        self.assertGreater(stale["A"], fresh["A"])
        self.assertEqual(0.0, fresh["B"])

    def test_composition_does_not_mutate_the_caller_manifest(self) -> None:
        data = _manifest(item("T-1", status="Ready"))

        compose_operational_state(data, _snapshot(_remote(status="Done")))

        self.assertEqual("Ready", data["items"][0]["status"])

    def test_the_planned_priority_field_uses_fresh_state(self) -> None:
        data = _manifest(
            item("A", status="Ready"),
            item("B", depends_on=["A"], status="Ready", impact=5, business_value=5),
        )
        snapshot = _snapshot(
            _remote("A", status="Ready", number=7),
            _remote("B", status="Done", number=8),
        )

        plan = build_sync_plan(data, snapshot, manage_body=False)

        planned = {
            action.item_id: action.payload["fields"]["Priority"]
            for action in plan.actions
            if "Priority" in action.payload.get("fields", {})
        }
        self.assertEqual(0.0, planned["B"])


if __name__ == "__main__":
    unittest.main()
