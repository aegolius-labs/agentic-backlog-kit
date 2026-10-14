"""S-R10-2: propose closing a parent once every child is closed.

Closure is supported by evidence, the children's closure, and still goes
through plan, digest confirmation, apply, and receipt. Nothing is ever closed
because the manifest stopped listing it.
"""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from agentic_backlog_kit.api_benchmark import SimulatedGitHub
from agentic_backlog_kit.capabilities import ACTION_CAPABILITIES
from agentic_backlog_kit.github import GitHubPlanExecutor, GitHubService
from agentic_backlog_kit.snapshot import GitHubSnapshotReader
from agentic_backlog_kit.sync import (
    ApplyAuthorizationError,
    SyncAction,
    apply_plan,
    build_sync_plan,
)
from agentic_backlog_kit.verification import verify_sync_apply

from tests.helpers import item, manifest


def _data() -> dict:
    return manifest(
        item("F-1", item_type="Story"),
        item("T-1", parent="F-1"),
        item("T-2", parent="F-1"),
    )


def _remote(item_id: str, number: int, *, state: str = "open", **extra) -> dict:
    base = {
        "abk_id": item_id,
        "number": number,
        "title": item_id,
        "body": "",
        "type": "Task",
        "state": state,
        "in_project": True,
        "parent_abk_id": None,
        "depends_on_abk_ids": [],
        "project_fields": {"Status": "Ready"},
    }
    base.update(extra)
    return base


def _snapshot(t1: str = "closed", t2: str = "closed", **parent) -> dict:
    return {
        "issues": [
            _remote("F-1", 1, **parent),
            _remote("T-1", 2, state=t1, parent_abk_id="F-1"),
            _remote("T-2", 3, state=t2, parent_abk_id="F-1"),
        ]
    }


def _closures(plan) -> list[SyncAction]:
    return [a for a in plan.actions if a.kind == "issue.close_parent"]


class ParentClosurePlanningTests(unittest.TestCase):
    def test_proposes_closing_and_marking_done_when_every_child_is_closed(
        self,
    ) -> None:
        plan = build_sync_plan(_data(), _snapshot())

        [closure] = _closures(plan)
        self.assertEqual("F-1", closure.item_id)
        self.assertEqual(
            {
                "state": "closed",
                "state_reason": "completed",
                "fields": {"Status": "Done"},
            },
            closure.payload,
        )
        self.assertEqual(
            {
                "T-1": {"number": 2, "state": "closed"},
                "T-2": {"number": 3, "state": "closed"},
            },
            closure.precondition["children"],
        )
        self.assertEqual(1, closure.precondition["issue"]["number"])
        self.assertIs(closure, plan.actions[-1])
        self.assertFalse(plan.priority_only)

    def test_never_proposed_while_any_child_is_open(self) -> None:
        self.assertEqual([], _closures(build_sync_plan(_data(), _snapshot(t2="open"))))

    def test_never_proposed_for_an_item_with_no_children(self) -> None:
        data = manifest(item("F-1", item_type="Story"))
        snapshot = {"issues": [_remote("F-1", 1)]}

        self.assertEqual([], _closures(build_sync_plan(data, snapshot)))

    def test_never_proposed_while_a_child_is_not_on_github(self) -> None:
        snapshot = _snapshot()
        snapshot["issues"].pop()

        self.assertEqual([], _closures(build_sync_plan(_data(), snapshot)))

    def test_a_closed_parent_is_left_alone(self) -> None:
        self.assertEqual(
            [], _closures(build_sync_plan(_data(), _snapshot(state="closed")))
        )

    def test_status_already_done_is_not_rewritten(self) -> None:
        plan = build_sync_plan(
            _data(), _snapshot(project_fields={"Status": "Done"})
        )

        [closure] = _closures(plan)
        self.assertNotIn("fields", closure.payload)

    def test_a_parent_outside_the_project_is_only_closed(self) -> None:
        plan = build_sync_plan(_data(), _snapshot(in_project=False))

        [closure] = _closures(plan)
        self.assertNotIn("fields", closure.payload)

    def test_the_parent_is_scored_as_the_done_item_it_will_become(self) -> None:
        open_children = build_sync_plan(_data(), _snapshot(t1="open", t2="open"))
        closed_children = build_sync_plan(_data(), _snapshot())

        def parent_priority(plan) -> float:
            fields = next(
                a.payload["fields"]
                for a in plan.actions
                if a.kind == "project.set_fields" and a.item_id == "F-1"
            )
            return fields["Priority"]

        self.assertGreater(parent_priority(open_children), 0)
        self.assertEqual(0, parent_priority(closed_children))

    def test_an_item_dropped_from_the_manifest_is_never_closed(self) -> None:
        data = manifest(item("T-1"))
        snapshot = {"issues": [_remote("T-1", 2), _remote("GONE", 9)]}

        plan = build_sync_plan(data, snapshot)

        self.assertEqual([], _closures(plan))
        self.assertNotIn("GONE", {a.item_id for a in plan.actions})

    def test_the_action_declares_its_capabilities(self) -> None:
        self.assertEqual(
            frozenset({"issue.write", "project.item.write"}),
            ACTION_CAPABILITIES["issue.close_parent"],
        )


class ParentClosureApplyTests(unittest.TestCase):
    def test_a_child_reopened_after_review_aborts_before_any_write(self) -> None:
        data = _data()
        plan = build_sync_plan(data, _snapshot())
        seen: list[str] = []

        with self.assertRaisesRegex(ApplyAuthorizationError, "drifted"):
            apply_plan(
                plan,
                executor=lambda action: seen.append(action.kind),
                confirmation=plan.digest,
                manifest=data,
                remote_snapshot=_snapshot(t1="open"),
            )
        self.assertEqual([], seen)

    def test_executor_closes_as_completed_then_marks_done(self) -> None:
        service = Mock()
        snapshot = {
            "issues": [
                {**_remote("F-1", 1), "id": 101, "node_id": "ISSUE_1"},
            ]
        }
        executor = GitHubPlanExecutor(service, remote_snapshot=snapshot)

        executor(
            SyncAction(
                "issue.close_parent",
                "F-1",
                {"state": "closed", "state_reason": "completed", "fields": {"Status": "Done"}},
            )
        )

        issue = service.close_issue.call_args.args[0]
        self.assertEqual(1, issue.number)
        self.assertEqual("completed", service.close_issue.call_args.args[1])
        service.set_project_fields.assert_called_once_with(issue, {"Status": "Done"})

    def test_end_to_end_closure_is_receipted_and_verified(self) -> None:
        data = _data()
        github = SimulatedGitHub(data)
        reader = GitHubSnapshotReader(
            github, owner="aegolius-labs", repository="example", project_number=1
        )
        service = GitHubService(
            github, owner="aegolius-labs", repository="example", project_number=1
        )

        def sync() -> object:
            snapshot = reader.read()
            plan = build_sync_plan(data, snapshot)
            receipt = apply_plan(
                plan,
                executor=GitHubPlanExecutor(service, remote_snapshot=snapshot),
                confirmation=plan.digest,
                manifest=data,
                remote_snapshot=snapshot,
            )
            return plan, receipt

        sync()
        for issue in github.issues[1:]:
            issue["state"] = "closed"

        plan, receipt = sync()

        self.assertEqual(["F-1"], [a.item_id for a in _closures(plan)])
        self.assertEqual("completed", receipt.status)
        self.assertIn(
            "issue.close_parent", [a["kind"] for a in receipt.completed_actions]
        )
        parent = github.issues[0]
        self.assertEqual(("closed", "completed"), (parent["state"], parent["state_reason"]))
        verification = verify_sync_apply(plan, data, reader.read, window=0)
        self.assertEqual("converged", verification.status)


if __name__ == "__main__":
    unittest.main()
