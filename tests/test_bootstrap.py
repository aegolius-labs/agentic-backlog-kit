from __future__ import annotations

import unittest

from agentic_backlog_kit.bootstrap import (
    BootstrapAuthorizationError,
    BootstrapExecutor,
    bootstrap_plan_from_dict,
    build_bootstrap_plan,
    apply_bootstrap_plan,
)
from agentic_backlog_kit.manifest import ManifestError


def discovery(*projects: dict) -> dict:
    return {
        "organization": {"login": "aegolius-labs", "id": "ORG_1"},
        "repository": {"name": "example", "id": "REPO_1"},
        "projects": list(projects),
        "labels": [],
    }


def project(number: int, title: str, *, linked: bool = False) -> dict:
    return {
        "id": f"PROJECT_{number}",
        "number": number,
        "title": title,
        "url": f"https://github.com/orgs/aegolius-labs/projects/{number}",
        "closed": False,
        "linked": linked,
        "fields": [],
        "views": [],
    }


class BootstrapPlanningTests(unittest.TestCase):
    def test_number_selects_exact_project_and_plans_repository_link(self) -> None:
        plan = build_bootstrap_plan(
            "aegolius-labs",
            "example",
            discovery(project(2, "Other"), project(7, "Backlog")),
            project_number=7,
        )

        self.assertEqual(7, plan.project["number"])
        self.assertEqual("project.link_repository", plan.actions[0].kind)
        self.assertNotIn("project.create", [action.kind for action in plan.actions])

    def test_title_match_is_exact_and_ambiguity_fails_closed(self) -> None:
        snapshot = discovery(project(2, "Backlog"), project(7, "Backlog"))

        with self.assertRaisesRegex(ManifestError, "ambiguous.*2, 7"):
            build_bootstrap_plan(
                "aegolius-labs", "example", snapshot, project_title="Backlog"
            )

    def test_no_selector_uses_unique_linked_or_repository_title_candidate(self) -> None:
        plan = build_bootstrap_plan(
            "aegolius-labs",
            "example",
            discovery(project(3, "Delivery", linked=True), project(8, "Other")),
        )

        self.assertEqual(3, plan.project["number"])
        self.assertNotIn(
            "project.link_repository", [action.kind for action in plan.actions]
        )

    def test_no_match_plans_explicit_project_creation_before_scaffold(self) -> None:
        plan = build_bootstrap_plan(
            "aegolius-labs", "example", discovery(), project_title="Product backlog"
        )

        self.assertIsNone(plan.project)
        self.assertEqual("project.create", plan.actions[0].kind)
        self.assertEqual(
            {
                "owner_id": "ORG_1",
                "repository_id": "REPO_1",
                "title": "Product backlog",
            },
            plan.actions[0].payload,
        )
        self.assertEqual(["project.create"], [action.kind for action in plan.actions])

    def test_apply_requires_digest_and_returns_created_identity(self) -> None:
        snapshot = discovery()
        plan = build_bootstrap_plan("aegolius-labs", "example", snapshot)
        service = FakeBootstrapService()

        with self.assertRaises(BootstrapAuthorizationError):
            apply_bootstrap_plan(
                plan,
                executor=BootstrapExecutor(service),
                confirmation="wrong",
                discovery_snapshot=snapshot,
            )

        result = apply_bootstrap_plan(
            plan,
            executor=BootstrapExecutor(service),
            confirmation=plan.digest,
            discovery_snapshot=snapshot,
        )

        self.assertEqual(11, result.project["number"])
        self.assertEqual("PROJECT_11", result.project["id"])
        self.assertEqual("project.create", service.calls[0][0])
        self.assertEqual(["project.create"], [call[0] for call in service.calls])

    def test_serialized_existing_project_plan_preserves_preconditions(self) -> None:
        plan = build_bootstrap_plan(
            "aegolius-labs", "example", discovery(project(7, "Backlog")),
            project_number=7,
        )

        restored = bootstrap_plan_from_dict(plan.as_dict())

        self.assertEqual(plan, restored)
        self.assertTrue(any(action.precondition for action in restored.actions))

    def test_fresh_discovery_drift_aborts_before_first_write(self) -> None:
        initial = discovery()
        plan = build_bootstrap_plan("aegolius-labs", "example", initial)
        service = FakeBootstrapService()

        with self.assertRaisesRegex(BootstrapAuthorizationError, "drifted"):
            apply_bootstrap_plan(
                plan,
                executor=BootstrapExecutor(service),
                confirmation=plan.digest,
                discovery_snapshot=discovery(project(9, "example", linked=True)),
            )

        self.assertEqual([], service.calls)

    def test_partial_failure_journals_completed_prefix(self) -> None:
        snapshot = discovery(project(7, "Backlog"))
        plan = build_bootstrap_plan(
            "aegolius-labs", "example", snapshot, project_number=7
        )
        service = FakeBootstrapService(fail_kind="project.field.create")
        receipts = []

        with self.assertRaisesRegex(RuntimeError, "injected"):
            apply_bootstrap_plan(
                plan,
                executor=BootstrapExecutor(service),
                confirmation=plan.digest,
                discovery_snapshot=snapshot,
                journal=receipts.append,
            )

        self.assertEqual("failed", receipts[-1].status)
        self.assertEqual("project.field.create", receipts[-1].failed_action["kind"])
        self.assertEqual("project.link_repository", receipts[-1].completed_actions[0]["kind"])


class FakeBootstrapService:
    def __init__(self, *, fail_kind: str | None = None) -> None:
        self.calls: list[tuple] = []
        self.fail_kind = fail_kind

    def _record(self, kind: str, payload: dict) -> None:
        if self.fail_kind == kind:
            raise RuntimeError("injected failure")
        self.calls.append((kind, payload))

    def use_project(self, identity: dict) -> None:
        self.calls.append(("project.use", identity["number"]))

    def create_project(self, payload: dict) -> dict:
        self._record("project.create", payload)
        return {
            "id": "PROJECT_11",
            "number": 11,
            "title": payload["title"],
            "url": "https://github.com/orgs/aegolius-labs/projects/11",
        }

    def link_project_repository(self, payload: dict) -> None:
        self._record("project.link_repository", payload)

    def create_project_field(self, payload: dict) -> None:
        self._record("project.field.create", payload)

    def update_project_field_options(self, payload: dict) -> None:
        self._record("project.field.update_options", payload)

    def create_label(self, payload: dict) -> None:
        self._record("repository.label.create", payload)

    def create_project_view(self, payload: dict) -> None:
        self._record("project.view.create", payload)

    def update_project_view(self, payload: dict) -> None:
        self._record("project.view.update", payload)


if __name__ == "__main__":
    unittest.main()
