from __future__ import annotations

import unittest

from agentic_backlog_kit.sync import ApplyAuthorizationError, apply_plan, build_sync_plan

from tests.helpers import item, manifest


class SyncPlanningTests(unittest.TestCase):
    def test_uses_configured_iteration_field_and_rejects_unresolved_alias(self) -> None:
        data = manifest(item("T-1", sprint="Sprint 11"))
        data["workflow"]["iteration"] = {
            "field": "Delivery Cycle",
            "start_date": "2026-08-03",
            "duration_days": 14,
        }

        plan = build_sync_plan(data, {"issues": []})

        add = next(action for action in plan.actions if action.kind == "project.add_item")
        self.assertEqual("Sprint 11", add.payload["fields"]["Delivery Cycle"])
        self.assertNotIn("Sprint", add.payload["fields"])

        data["items"][0]["sprint"] = "@next"
        with self.assertRaisesRegex(Exception, "resolved"):
            build_sync_plan(data, {"issues": []})

    def test_plans_create_before_relationship_actions(self) -> None:
        data = manifest(
            item("T-BASE"),
            item("T-VALUE", depends_on=["T-BASE"]),
        )

        plan = build_sync_plan(data, {"issues": []})

        self.assertEqual(
            [
                "issue.create",
                "issue.create",
                "project.add_item",
                "project.add_item",
                "issue.add_dependency",
            ],
            [action.kind for action in plan.actions],
        )
        self.assertEqual("T-VALUE", plan.actions[-1].item_id)
        self.assertEqual("T-BASE", plan.actions[-1].payload["depends_on"])

    def test_identical_remote_state_produces_no_actions(self) -> None:
        local_item = item("T-1", title="Ship it")
        data = manifest(local_item)
        remote = {
            "issues": [
                {
                    "abk_id": "T-1",
                    "number": 42,
                    "title": "Ship it",
                    "body": "",
                    "type": "Task",
                    "state": "open",
                    "in_project": True,
                    "parent_abk_id": None,
                    "depends_on_abk_ids": [],
                    "project_fields": {
                        "Status": "Ready",
                        "Impact": 3,
                        "Effort": 3,
                        "Business Value": 3,
                        "Enabler Value": 0,
                        "Priority": 15.0,
                    },
                }
            ]
        }

        plan = build_sync_plan(data, remote, manage_body=False)

        self.assertEqual([], plan.actions)

    def test_apply_requires_an_explicit_confirmation_token(self) -> None:
        plan = build_sync_plan(manifest(item("T-1")), {"issues": []})

        with self.assertRaises(ApplyAuthorizationError):
            apply_plan(plan, executor=lambda action: None, confirmation=None)

    def test_apply_executes_the_validated_plan_in_order(self) -> None:
        data = manifest(item("T-1"))
        snapshot = {"issues": []}
        plan = build_sync_plan(data, snapshot)
        seen: list[str] = []

        receipt = apply_plan(
            plan,
            executor=lambda action: seen.append(action.kind),
            confirmation=plan.digest,
            manifest=data,
            remote_snapshot=snapshot,
        )

        self.assertEqual([action.kind for action in plan.actions], seen)
        self.assertEqual(plan.digest, receipt.plan_digest)
        self.assertEqual(len(plan.actions), receipt.applied_actions)
        self.assertEqual("completed", receipt.status)

    def test_plan_digest_binds_manifest_snapshot_and_action_preconditions(self) -> None:
        data = manifest(item("T-1"))
        snapshot = {"issues": []}

        plan = build_sync_plan(data, snapshot)

        self.assertEqual(64, len(plan.manifest_fingerprint))
        self.assertEqual(64, len(plan.snapshot_fingerprint))
        self.assertEqual({"issue": None}, plan.actions[0].precondition)
        payload = plan.as_dict()
        self.assertEqual(plan.manifest_fingerprint, payload["manifest_fingerprint"])
        self.assertIn("precondition", payload["actions"][0])

    def test_local_or_remote_drift_aborts_before_first_write(self) -> None:
        data = manifest(item("T-1"))
        snapshot = {"issues": []}
        plan = build_sync_plan(data, snapshot)
        writes: list[str] = []

        changed = manifest(item("T-1", title="Changed after review"))
        with self.assertRaisesRegex(ApplyAuthorizationError, "drift"):
            apply_plan(
                plan,
                executor=lambda action: writes.append(action.kind),
                confirmation=plan.digest,
                manifest=changed,
                remote_snapshot=snapshot,
            )
        self.assertEqual([], writes)

        remote_changed = {"issues": [{"abk_id": "T-9", "title": "Concurrent"}]}
        with self.assertRaisesRegex(ApplyAuthorizationError, "drift"):
            apply_plan(
                plan,
                executor=lambda action: writes.append(action.kind),
                confirmation=plan.digest,
                manifest=data,
                remote_snapshot=remote_changed,
            )
        self.assertEqual([], writes)

    def test_partial_failure_journals_completed_prefix_and_failure(self) -> None:
        data = manifest(item("T-1"), item("T-2"))
        snapshot = {"issues": []}
        plan = build_sync_plan(data, snapshot)
        journal = []
        calls = 0

        def fail_second(action):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected failure")

        with self.assertRaisesRegex(RuntimeError, "injected failure"):
            apply_plan(
                plan,
                executor=fail_second,
                confirmation=plan.digest,
                manifest=data,
                remote_snapshot=snapshot,
                journal=journal.append,
            )

        receipt = journal[-1]
        self.assertEqual("failed", receipt.status)
        self.assertEqual(1, receipt.applied_actions)
        self.assertEqual([plan.actions[0].as_dict()], receipt.completed_actions)
        self.assertEqual(plan.actions[1].as_dict(), receipt.failed_action)
        self.assertIn("injected failure", receipt.error)

    def test_interrupted_apply_requires_verified_replan_for_remaining_work(self) -> None:
        data = manifest(item("T-1", title="New title"))
        before = {
            "issues": [
                {
                    "abk_id": "T-1",
                    "title": "Old title",
                    "body": "",
                    "type": "Task",
                    "in_project": False,
                    "parent_abk_id": None,
                    "depends_on_abk_ids": [],
                }
            ]
        }
        reviewed = build_sync_plan(data, before, manage_body=False)
        after_first_action = {
            "issues": [{**before["issues"][0], "title": "New title"}]
        }

        with self.assertRaisesRegex(ApplyAuthorizationError, "drift"):
            apply_plan(
                reviewed,
                executor=lambda action: None,
                confirmation=reviewed.digest,
                manifest=data,
                remote_snapshot=after_first_action,
            )

        remaining = build_sync_plan(data, after_first_action, manage_body=False)
        self.assertEqual(["project.add_item"], [a.kind for a in remaining.actions])
        receipt = apply_plan(
            remaining,
            executor=lambda action: None,
            confirmation=remaining.digest,
            manifest=data,
            remote_snapshot=after_first_action,
        )
        self.assertEqual("completed", receipt.status)
        self.assertEqual(1, receipt.applied_actions)

    def test_type_change_preserves_unmanaged_remote_labels(self) -> None:
        local_item = item("T-1", item_type="Task")
        remote = {
            "issues": [
                {
                    "abk_id": "T-1",
                    "title": "T-1",
                    "body": "",
                    "type": "Story",
                    "labels": ["customer", "type:story"],
                    "in_project": False,
                    "parent_abk_id": None,
                    "depends_on_abk_ids": [],
                }
            ]
        }

        plan = build_sync_plan(manifest(local_item), remote, manage_body=False)
        update = next(action for action in plan.actions if action.kind == "issue.update")

        self.assertEqual(["customer", "type:task"], update.payload["labels"])


if __name__ == "__main__":
    unittest.main()
