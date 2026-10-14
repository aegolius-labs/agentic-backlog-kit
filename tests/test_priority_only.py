"""S-R10-4: a plan made solely of Priority field updates is pre-authorized.

Owner decision 2026-09-24. The engine, not an agent reading the plan, decides
whether the exemption applies, and the plan stays bound to fresh state.
"""

from __future__ import annotations

import unittest

from agentic_backlog_kit.sync import (
    DIGEST_AUTHORIZATION,
    PRIORITY_ONLY_AUTHORIZATION,
    ApplyAuthorizationError,
    SyncAction,
    apply_plan,
    build_sync_plan,
    compute_title_digest,
    is_priority_only,
    render_written_comment,
    sync_plan_from_dict,
)

from tests.helpers import item, manifest


def _snapshot(*, priority: float = 15.0, title: str = "Ship it", **fields) -> dict:
    project_fields = {
        "Status": "Ready",
        "Impact": 3,
        "Effort": 3,
        "Business Value": 3,
        "Enabler Value": 0,
        "Priority": priority,
    }
    project_fields.update(fields)
    return {
        "issues": [
            {
                "abk_id": "T-1",
                "number": 42,
                "title": title,
                "body": render_written_comment(compute_title_digest(title), None),
                "type": "Task",
                "state": "open",
                "in_project": True,
                "parent_abk_id": None,
                "depends_on_abk_ids": [],
                "project_fields": project_fields,
            }
        ]
    }


def _plan(snapshot: dict, data: dict | None = None):
    data = data or manifest(item("T-1", title="Ship it"))
    return data, build_sync_plan(data, snapshot, manage_body=False)


class PriorityOnlyRecognitionTests(unittest.TestCase):
    def test_a_stale_priority_alone_yields_a_priority_only_plan(self) -> None:
        _, plan = _plan(_snapshot(priority=99.0))

        self.assertEqual(["project.set_fields"], [a.kind for a in plan.actions])
        self.assertTrue(plan.priority_only)
        self.assertTrue(plan.as_dict()["priority_only"])

    def test_any_other_field_disqualifies_the_plan(self) -> None:
        _, plan = _plan(_snapshot(priority=99.0, Impact=1))

        self.assertEqual(
            {"Priority", "Impact"}, set(plan.actions[0].payload["fields"])
        )
        self.assertFalse(plan.priority_only)

    def test_any_other_action_kind_disqualifies_the_plan(self) -> None:
        _, plan = _plan(_snapshot(priority=99.0, title="Edited elsewhere"))

        self.assertIn("issue.update", [a.kind for a in plan.actions])
        self.assertFalse(plan.priority_only)

    def test_an_empty_plan_is_not_priority_only(self) -> None:
        _, plan = _plan(_snapshot())

        self.assertEqual([], plan.actions)
        self.assertFalse(plan.priority_only)

    def test_extra_payload_keys_disqualify_an_action(self) -> None:
        priority = SyncAction("project.set_fields", "T-1", {"fields": {"Priority": 1}})
        smuggled = SyncAction(
            "project.set_fields",
            "T-1",
            {"fields": {"Priority": 1}, "status": "Done"},
        )

        self.assertTrue(is_priority_only([priority]))
        self.assertFalse(is_priority_only([priority, smuggled]))

    def test_a_plan_file_cannot_claim_the_exemption(self) -> None:
        _, plan = _plan(_snapshot(priority=99.0, Impact=1))
        payload = plan.as_dict()
        payload["priority_only"] = True

        self.assertFalse(sync_plan_from_dict(payload).priority_only)


class PriorityOnlyApplyTests(unittest.TestCase):
    def test_applies_without_confirmation_and_records_the_basis(self) -> None:
        snapshot = _snapshot(priority=99.0)
        data, plan = _plan(snapshot)
        seen: list[str] = []

        receipt = apply_plan(
            plan,
            executor=lambda action: seen.append(action.kind),
            confirmation=None,
            manifest=data,
            remote_snapshot=snapshot,
        )

        self.assertEqual(["project.set_fields"], seen)
        self.assertEqual("completed", receipt.status)
        self.assertEqual(plan.digest, receipt.plan_digest)
        self.assertEqual(PRIORITY_ONLY_AUTHORIZATION, receipt.authorization)

    def test_a_confirmed_plan_records_digest_authorization(self) -> None:
        snapshot = _snapshot(priority=99.0)
        data, plan = _plan(snapshot)

        receipt = apply_plan(
            plan,
            executor=lambda action: None,
            confirmation=plan.digest,
            manifest=data,
            remote_snapshot=snapshot,
        )

        self.assertEqual(DIGEST_AUTHORIZATION, receipt.authorization)

    def test_a_wrong_confirmation_is_refused_even_for_a_priority_only_plan(
        self,
    ) -> None:
        snapshot = _snapshot(priority=99.0)
        data, plan = _plan(snapshot)

        with self.assertRaises(ApplyAuthorizationError):
            apply_plan(
                plan,
                executor=lambda action: None,
                confirmation="0" * 64,
                manifest=data,
                remote_snapshot=snapshot,
            )

    def test_any_other_plan_is_refused_without_confirmation(self) -> None:
        snapshot = _snapshot(priority=99.0, Impact=1)
        data, plan = _plan(snapshot)
        seen: list[str] = []

        with self.assertRaisesRegex(ApplyAuthorizationError, "Priority"):
            apply_plan(
                plan,
                executor=lambda action: seen.append(action.kind),
                confirmation=None,
                manifest=data,
                remote_snapshot=snapshot,
            )
        self.assertEqual([], seen)

    def test_still_bound_to_fresh_state(self) -> None:
        reviewed = _snapshot(priority=99.0)
        data, plan = _plan(reviewed)
        # Someone retitled the issue after the plan was made: the fresh plan
        # differs, so the exemption cannot carry the new change.
        fresh = _snapshot(priority=99.0, title="Edited elsewhere")
        seen: list[str] = []

        with self.assertRaisesRegex(ApplyAuthorizationError, "drifted"):
            apply_plan(
                plan,
                executor=lambda action: seen.append(action.kind),
                confirmation=None,
                manifest=data,
                remote_snapshot=fresh,
            )
        self.assertEqual([], seen)

    def test_a_tampered_plan_is_refused(self) -> None:
        snapshot = _snapshot(priority=99.0)
        data, plan = _plan(snapshot)
        plan.actions[0].payload["fields"]["Priority"] = 0.0

        with self.assertRaises(ApplyAuthorizationError):
            apply_plan(
                plan,
                executor=lambda action: None,
                confirmation=None,
                manifest=data,
                remote_snapshot=snapshot,
            )


if __name__ == "__main__":
    unittest.main()
