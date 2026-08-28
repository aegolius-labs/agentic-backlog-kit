from __future__ import annotations

import unittest

from agentic_backlog_kit.sync import ApplyAuthorizationError, apply_plan, build_sync_plan

from tests.helpers import item, manifest


class SyncPlanningTests(unittest.TestCase):
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
        plan = build_sync_plan(manifest(item("T-1")), {"issues": []})
        seen: list[str] = []

        receipt = apply_plan(
            plan,
            executor=lambda action: seen.append(action.kind),
            confirmation=plan.digest,
        )

        self.assertEqual([action.kind for action in plan.actions], seen)
        self.assertEqual(plan.digest, receipt.plan_digest)
        self.assertEqual(len(plan.actions), receipt.applied_actions)

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
