from __future__ import annotations

import unittest

from agentic_backlog_kit.manifest import ManifestError
from agentic_backlog_kit.sync import (
    ApplyAuthorizationError,
    apply_plan,
    build_sync_plan,
    extract_item_id,
    extract_marker_fields,
    extract_written_digest,
    render_issue_body,
    render_marker,
    with_written_comment,
)

from tests.helpers import item, manifest


def _remote(item_id: str, *, title: str, body: str, number: int = 1, **overrides) -> dict:
    base = {
        "abk_id": item_id,
        "number": number,
        "title": title,
        "body": body,
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
    base.update(overrides)
    return base


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


class RemoteEditHoldTests(unittest.TestCase):
    """R35: hold a title/body update GitHub reports a human changed since the

    kit's last write, rather than silently reverting it.
    """

    def _baseline(self, local_item: dict) -> str:
        return with_written_comment(local_item["title"], render_issue_body(local_item))

    def test_absent_baseline_plans_the_update_and_writes_one(self) -> None:
        local_item = item("T-1", title="Ship it")
        remote = {
            "issues": [_remote("T-1", title="Old title", body="")]
        }

        plan = build_sync_plan(manifest(local_item), remote)

        self.assertEqual([], plan.held_remote_edits)
        update = next(a for a in plan.actions if a.kind == "issue.update")
        self.assertEqual("Ship it", update.payload["title"])
        self.assertEqual(
            with_written_comment("Ship it", render_issue_body(local_item)),
            update.payload["body"],
        )
        self.assertIsNotNone(extract_written_digest(update.payload["body"]))

    def test_no_hold_when_baseline_matches_and_manifest_wants_a_further_change(
        self,
    ) -> None:
        local_item = item("T-1", title="Ship it")
        written_before = item("T-1", title="Ship it earlier")
        baseline_body = self._baseline(written_before)
        remote = {
            "issues": [_remote("T-1", title="Ship it earlier", body=baseline_body)]
        }

        plan = build_sync_plan(manifest(local_item), remote)

        self.assertEqual([], plan.held_remote_edits)
        update = next(a for a in plan.actions if a.kind == "issue.update")
        self.assertEqual("Ship it", update.payload["title"])

    def test_holds_a_title_edited_on_github_since_the_last_write(self) -> None:
        local_item = item("T-1", title="Ship it")
        baseline_body = self._baseline(local_item)
        remote = {
            "issues": [
                _remote("T-1", title="Ship it differently", body=baseline_body, number=7)
            ]
        }

        plan = build_sync_plan(manifest(local_item), remote)

        self.assertEqual([], [a for a in plan.actions if a.kind == "issue.update"])
        self.assertEqual(
            [
                {
                    "item_id": "T-1",
                    "issue_number": 7,
                    "fields": ["title"],
                    "reason": "edited on GitHub since the kit last wrote it",
                    "hint": (
                        "Update the manifest item to accept the GitHub edit, or "
                        "pass --overwrite-remote-edit T-1 to restore the "
                        "manifest's version"
                    ),
                }
            ],
            plan.held_remote_edits,
        )

    def test_holds_a_body_edited_on_github_since_the_last_write(self) -> None:
        local_item = item("T-1", title="Ship it")
        baseline_body = self._baseline(local_item)
        edited_body = baseline_body.replace(
            "## Outcome", "## Outcome\n\nA human added this line.\n"
        )
        remote = {"issues": [_remote("T-1", title="Ship it", body=edited_body)]}

        plan = build_sync_plan(manifest(local_item), remote)

        self.assertEqual([], [a for a in plan.actions if a.kind == "issue.update"])
        self.assertEqual(1, len(plan.held_remote_edits))
        self.assertEqual(["body"], plan.held_remote_edits[0]["fields"])

    def test_no_hold_when_the_remote_already_matches_what_the_manifest_wants(
        self,
    ) -> None:
        local_item = item("T-1", title="Ship it")
        correct_body = self._baseline(local_item)
        real_digest = extract_written_digest(correct_body)
        bogus_digest = ("0" if real_digest[0] != "0" else "1") + real_digest[1:]
        # A stale/bogus baseline digest: on its own it looks like the remote
        # was edited since the kit's last write, but the content already is
        # exactly what the manifest wants, so there is nothing to hold or plan.
        tampered_body = correct_body.replace(real_digest, bogus_digest)
        remote = {"issues": [_remote("T-1", title="Ship it", body=tampered_body)]}

        plan = build_sync_plan(manifest(local_item), remote)

        self.assertEqual([], plan.held_remote_edits)
        self.assertEqual([], [a for a in plan.actions if a.kind == "issue.update"])

    def test_crlf_normalization_does_not_register_as_an_edit(self) -> None:
        local_item = item("T-1", title="Ship it")
        baseline_body = self._baseline(local_item)
        remote = {
            "issues": [
                _remote("T-1", title="Ship it", body=baseline_body.replace("\n", "\r\n"))
            ]
        }

        plan = build_sync_plan(manifest(local_item), remote)

        self.assertEqual([], plan.held_remote_edits)
        self.assertEqual([], [a for a in plan.actions if a.kind == "issue.update"])

    def test_title_only_change_still_rewrites_the_body_to_refresh_the_digest(
        self,
    ) -> None:
        local_item = item("T-1", title="Renamed")
        written_before = item("T-1", title="Original name")
        baseline_body = self._baseline(written_before)
        remote = {
            "issues": [_remote("T-1", title="Original name", body=baseline_body)]
        }

        plan = build_sync_plan(manifest(local_item), remote)

        update = next(a for a in plan.actions if a.kind == "issue.update")
        self.assertEqual("Renamed", update.payload["title"])
        self.assertIn("body", update.payload)
        self.assertNotEqual(
            extract_written_digest(baseline_body),
            extract_written_digest(update.payload["body"]),
        )

    def test_override_restores_the_manifests_version_of_a_held_item(self) -> None:
        local_item = item("T-1", title="Ship it")
        baseline_body = self._baseline(local_item)
        remote = {
            "issues": [_remote("T-1", title="Ship it differently", body=baseline_body)]
        }

        plan = build_sync_plan(
            manifest(local_item), remote, overwrite_remote_edits=["T-1"]
        )

        self.assertEqual([], plan.held_remote_edits)
        self.assertEqual(["T-1"], plan.overwrite_remote_edits)
        update = next(a for a in plan.actions if a.kind == "issue.update")
        self.assertEqual("Ship it", update.payload["title"])

    def test_override_of_a_non_held_item_is_rejected(self) -> None:
        local_item = item("T-1", title="Ship it")
        remote = {"issues": [_remote("T-1", title="Ship it", body="")]}

        with self.assertRaisesRegex(ManifestError, "not held"):
            build_sync_plan(manifest(local_item), remote, overwrite_remote_edits=["T-1"])

    def test_override_of_an_unknown_item_is_rejected(self) -> None:
        with self.assertRaisesRegex(ManifestError, "unknown"):
            build_sync_plan(
                manifest(item("T-1")),
                {"issues": []},
                overwrite_remote_edits=["NOT-AN-ITEM"],
            )

    def test_held_edits_are_folded_into_the_plan_digest(self) -> None:
        local_item = item("T-1", title="Ship it")
        baseline_body = self._baseline(local_item)
        held_remote = {
            "issues": [_remote("T-1", title="Ship it differently", body=baseline_body)]
        }
        clean_remote = {"issues": [_remote("T-1", title="Ship it", body=baseline_body)]}

        held_plan = build_sync_plan(manifest(local_item), held_remote)
        clean_plan = build_sync_plan(manifest(local_item), clean_remote)

        self.assertNotEqual(held_plan.digest, clean_plan.digest)

    def test_extract_functions_ignore_the_written_comment(self) -> None:
        local_item = item("T-1", title="Ship it")
        body = with_written_comment(local_item["title"], render_issue_body(local_item))

        self.assertEqual("T-1", extract_item_id(body))
        fields = extract_marker_fields(body)
        self.assertEqual({"id": "T-1", "schema": "1"}, fields)
        self.assertNotIn("written", fields)
        self.assertEqual(render_marker(local_item), body.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
