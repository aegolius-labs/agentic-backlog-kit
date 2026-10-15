"""S-R10-3: remove relationships the manifest no longer declares.

Only links between two manifest items are removed, each removal records what
restores it, and no issue is closed or deleted.
"""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from agentic_backlog_kit.api_benchmark import SimulatedGitHub
from agentic_backlog_kit.capabilities import ACTION_CAPABILITIES
from agentic_backlog_kit.github import GitHubPlanExecutor, GitHubService
from agentic_backlog_kit.snapshot import GitHubSnapshotReader
from agentic_backlog_kit.sync import SyncAction, apply_plan, build_sync_plan
from agentic_backlog_kit.verification import verify_sync_apply

from tests.helpers import item, manifest


def _remote(item_id: str, number: int, **extra) -> dict:
    base = {
        "abk_id": item_id,
        "number": number,
        "title": item_id,
        "body": "",
        "type": "Task",
        "state": "open",
        "in_project": True,
        "parent_abk_id": None,
        "depends_on_abk_ids": [],
        "project_fields": {},
    }
    base.update(extra)
    return base


def _removals(plan) -> list[SyncAction]:
    return [a for a in plan.actions if a.kind.startswith("issue.remove_")]


class RelationshipRemovalPlanningTests(unittest.TestCase):
    def test_a_dropped_parent_is_removed_with_its_restore_record(self) -> None:
        data = manifest(item("S-1", item_type="Story"), item("T-1"))
        snapshot = {
            "issues": [_remote("S-1", 1), _remote("T-1", 2, parent_abk_id="S-1")]
        }

        [removal] = _removals(build_sync_plan(data, snapshot))

        self.assertEqual(("issue.remove_parent", "T-1"), (removal.kind, removal.item_id))
        self.assertEqual("S-1", removal.payload["parent"])
        self.assertEqual(
            {
                "kind": "issue.set_parent",
                "item_id": "T-1",
                "payload": {"parent": "S-1"},
                "issue_number": 2,
                "parent_issue_number": 1,
            },
            removal.payload["restore"],
        )

    def test_a_changed_parent_is_replaced_not_removed(self) -> None:
        data = manifest(
            item("S-1", item_type="Story"),
            item("S-2", item_type="Story"),
            item("T-1", parent="S-2"),
        )
        snapshot = {
            "issues": [
                _remote("S-1", 1),
                _remote("S-2", 3),
                _remote("T-1", 2, parent_abk_id="S-1"),
            ]
        }

        plan = build_sync_plan(data, snapshot)

        self.assertEqual([], _removals(plan))
        self.assertIn("issue.set_parent", [a.kind for a in plan.actions])

    def test_a_dropped_dependency_is_removed_with_its_restore_record(self) -> None:
        data = manifest(item("T-1"), item("T-2"))
        snapshot = {
            "issues": [_remote("T-1", 1), _remote("T-2", 2, depends_on_abk_ids=["T-1"])]
        }

        [removal] = _removals(build_sync_plan(data, snapshot))

        self.assertEqual("issue.remove_dependency", removal.kind)
        self.assertEqual("T-2", removal.item_id)
        self.assertEqual(
            {
                "kind": "issue.add_dependency",
                "item_id": "T-2",
                "payload": {"depends_on": "T-1"},
                "issue_number": 2,
                "blocker_issue_number": 1,
            },
            removal.payload["restore"],
        )

    def test_links_to_issues_outside_the_manifest_are_never_removed(self) -> None:
        # OTHER carries a kit marker but is not in this manifest.
        data = manifest(item("T-1"))
        snapshot = {
            "issues": [
                _remote("T-1", 1, parent_abk_id="OTHER", depends_on_abk_ids=["OTHER"]),
                _remote("OTHER", 9),
            ]
        }

        self.assertEqual([], _removals(build_sync_plan(data, snapshot)))

    def test_declared_links_are_kept(self) -> None:
        data = manifest(
            item("S-1", item_type="Story"),
            item("T-1", parent="S-1"),
            item("T-2", depends_on=["T-1"]),
        )
        snapshot = {
            "issues": [
                _remote("S-1", 1),
                _remote("T-1", 2, parent_abk_id="S-1"),
                _remote("T-2", 3, depends_on_abk_ids=["T-1"]),
            ]
        }

        self.assertEqual([], _removals(build_sync_plan(data, snapshot)))

    def test_removals_precede_additions_so_a_reversal_never_forms_a_cycle(
        self,
    ) -> None:
        data = manifest(item("T-1", depends_on=["T-2"]), item("T-2"))
        snapshot = {
            "issues": [_remote("T-1", 1), _remote("T-2", 2, depends_on_abk_ids=["T-1"])]
        }

        kinds = [a.kind for a in build_sync_plan(data, snapshot).actions]

        self.assertLess(
            kinds.index("issue.remove_dependency"), kinds.index("issue.add_dependency")
        )

    def test_removal_never_closes_or_deletes_an_issue(self) -> None:
        data = manifest(item("T-1"), item("T-2"))
        snapshot = {
            "issues": [_remote("T-1", 1), _remote("T-2", 2, depends_on_abk_ids=["T-1"])]
        }

        kinds = {a.kind for a in build_sync_plan(data, snapshot).actions}

        self.assertFalse(kinds & {"issue.close_parent", "issue.delete", "issue.close"})

    def test_actions_declare_their_capabilities(self) -> None:
        self.assertEqual(
            frozenset({"issue.hierarchy"}), ACTION_CAPABILITIES["issue.remove_parent"]
        )
        self.assertEqual(
            frozenset({"issue.dependency"}),
            ACTION_CAPABILITIES["issue.remove_dependency"],
        )


class RelationshipRemovalApplyTests(unittest.TestCase):
    def test_executor_calls_the_matching_service_methods(self) -> None:
        service = Mock()
        snapshot = {
            "issues": [
                {**_remote("A", 1), "id": 101, "node_id": "I_1"},
                {**_remote("B", 2), "id": 102, "node_id": "I_2"},
            ]
        }
        executor = GitHubPlanExecutor(service, remote_snapshot=snapshot)

        executor(SyncAction("issue.remove_parent", "B", {"parent": "A"}))
        executor(SyncAction("issue.remove_dependency", "B", {"depends_on": "A"}))

        child, parent = service.remove_parent.call_args.args
        self.assertEqual((2, 1), (child.number, parent.number))
        issue, blocker = service.remove_dependency.call_args.args
        self.assertEqual((2, 1), (issue.number, blocker.number))

    def test_service_sends_the_documented_rest_calls(self) -> None:
        transport = Mock()
        service = GitHubService(
            transport, owner="o", repository="r", project_number=1
        )
        child = Mock(number=2, database_id=102)
        parent = Mock(number=1, database_id=101)

        service.remove_parent(child, parent)
        service.remove_dependency(child, parent)

        self.assertEqual(
            [
                (("DELETE", "/repos/o/r/issues/1/sub_issue", {"sub_issue_id": 102}),),
                (("DELETE", "/repos/o/r/issues/2/dependencies/blocked_by/101"),),
            ],
            [(call.args,) for call in transport.rest.call_args_list],
        )

    def test_end_to_end_removal_converges(self) -> None:
        declared = manifest(
            item("S-1", item_type="Story"),
            item("T-1", parent="S-1"),
            item("T-2", depends_on=["T-1"]),
        )
        github = SimulatedGitHub(declared)
        reader = GitHubSnapshotReader(
            github, owner="aegolius-labs", repository="example", project_number=1
        )
        service = GitHubService(
            github, owner="aegolius-labs", repository="example", project_number=1
        )

        def sync(data: dict):
            snapshot = reader.read()
            plan = build_sync_plan(data, snapshot)
            apply_plan(
                plan,
                executor=GitHubPlanExecutor(service, remote_snapshot=snapshot),
                confirmation=plan.digest,
                manifest=data,
                remote_snapshot=snapshot,
            )
            return plan

        sync(declared)
        self.assertTrue(github.parents and any(github.blocked_by.values()))

        dropped = manifest(item("S-1", item_type="Story"), item("T-1"), item("T-2"))
        plan = sync(dropped)

        self.assertEqual(
            ["issue.remove_parent", "issue.remove_dependency"],
            [a.kind for a in _removals(plan)],
        )
        self.assertEqual({}, github.parents)
        self.assertFalse(any(github.blocked_by.values()))
        self.assertEqual(3, len(github.issues))
        self.assertTrue(all(issue["state"] == "open" for issue in github.issues))
        verification = verify_sync_apply(plan, dropped, reader.read, window=0)
        self.assertEqual("converged", verification.status)


if __name__ == "__main__":
    unittest.main()
