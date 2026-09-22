from __future__ import annotations

import unittest

from agentic_backlog_kit.importing import (
    ImportExecutor,
    adopted_body,
    apply_import_plan,
    build_import_plan,
    find_orphans,
    import_plan_from_dict,
    merge_imported_items,
    proposed_item_id,
    reconcile_orphans,
)
from agentic_backlog_kit.manifest import ManifestError
from agentic_backlog_kit.sync import ApplyAuthorizationError, extract_item_id

from tests.helpers import item, manifest


def _issue(
    number: int,
    *,
    title: str | None = None,
    body: str = "",
    state: str = "open",
    issue_type: str | None = None,
    labels: list[str] | None = None,
) -> dict:
    return {
        "number": number,
        "node_id": f"I_{number}",
        "url": f"https://github.com/o/r/issues/{number}",
        "title": title if title is not None else f"Existing issue {number}",
        "body": body,
        "state": state,
        "labels": labels or [],
        "type": issue_type,
    }


class ImportPreviewTests(unittest.TestCase):
    """R11 - previewing an import reads and writes nothing."""

    def test_proposes_one_item_per_unmanaged_issue(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7), _issue(9)])

        self.assertEqual(["GH-7", "GH-9"], [entry["id"] for entry in plan.items])
        self.assertEqual(2, len(plan.actions))

    def test_every_action_only_adopts(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7)])

        self.assertEqual({"issue.adopt"}, {action.kind for action in plan.actions})

    def test_an_unselected_issue_is_reported_and_untouched(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7), _issue(9)], include={7})

        self.assertEqual(["GH-7"], [entry["id"] for entry in plan.items])
        self.assertEqual("not selected", plan.skipped["#9"])

    def test_a_limit_bounds_the_first_adoption(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7), _issue(9)], limit=1)

        self.assertEqual(["GH-7"], [entry["id"] for entry in plan.items])
        self.assertIn("limit", plan.skipped["#9"])

    def test_rejects_a_selection_that_is_not_unmanaged(self) -> None:
        with self.assertRaisesRegex(ManifestError, "not unmanaged"):
            build_import_plan(manifest(), [_issue(7)], include={7, 404})

    def test_rejects_a_non_positive_limit(self) -> None:
        with self.assertRaisesRegex(ManifestError, "positive integer"):
            build_import_plan(manifest(), [_issue(7)], limit=0)


class InferenceTests(unittest.TestCase):
    def test_maps_a_known_issue_type(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7, issue_type="Bug")])

        self.assertEqual("Bug", plan.items[0]["type"])

    def test_maps_an_organization_specific_story_type(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7, issue_type="User Story")])

        self.assertEqual("Story", plan.items[0]["type"])

    def test_falls_back_for_a_type_the_manifest_does_not_know(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7, issue_type="Theme")])

        self.assertEqual("Task", plan.items[0]["type"])

    def test_a_closed_issue_adopts_as_complete(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7, state="closed")])

        self.assertEqual("Done", plan.items[0]["status"])

    def test_an_open_issue_adopts_unrefined(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7)])

        self.assertEqual("Inbox", plan.items[0]["status"])
        self.assertEqual("idea", plan.items[0]["maturity"])

    def test_keeps_the_existing_body_as_the_description(self) -> None:
        plan = build_import_plan(
            manifest(), [_issue(7, body="Real content someone wrote.")]
        )

        self.assertEqual("Real content someone wrote.", plan.items[0]["description"])

    def test_falls_back_to_the_title_for_an_empty_body(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7, title="Fix the thing")])

        self.assertEqual("Fix the thing", plan.items[0]["description"])

    def test_skips_an_issue_with_no_title(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7, title="   ")])

        self.assertEqual([], plan.items)
        self.assertIn("no title", plan.skipped["#7"])


class DuplicateTests(unittest.TestCase):
    """R11 - duplicate mappings are rejected."""

    def test_rejects_an_issue_the_manifest_already_claims(self) -> None:
        data = manifest(item("GH-7"))

        with self.assertRaisesRegex(ManifestError, "duplicate item id"):
            build_import_plan(data, [_issue(7)])

    def test_withholds_an_issue_whose_title_is_already_managed(self) -> None:
        data = manifest(item("T-1", title="Fix the thing"))

        plan = build_import_plan(data, [_issue(7, title="Fix the thing")])

        self.assertEqual([], plan.items)
        self.assertIn("already has this title", plan.skipped["#7"])

    def test_an_explicit_override_adopts_a_duplicate_title(self) -> None:
        data = manifest(item("T-1", title="Fix the thing"))

        plan = build_import_plan(
            data, [_issue(7, title="Fix the thing")], allow_duplicate_titles=True
        )

        self.assertEqual(["GH-7"], [entry["id"] for entry in plan.items])

    def test_merging_twice_is_refused(self) -> None:
        data = manifest()
        plan = build_import_plan(data, [_issue(7)])
        once = merge_imported_items(data, plan.items)

        with self.assertRaisesRegex(ManifestError, "already contains"):
            merge_imported_items(once, plan.items)


class AdoptedBodyTests(unittest.TestCase):
    def test_prepends_the_marker_and_keeps_the_content(self) -> None:
        body = adopted_body("GH-7", "Line one\n\nLine two")

        self.assertEqual("GH-7", extract_item_id(body))
        self.assertIn("Line one", body)
        self.assertIn("Line two", body)

    def test_handles_an_empty_body(self) -> None:
        body = adopted_body("GH-7", "")

        self.assertEqual("GH-7", extract_item_id(body))

    def test_the_planned_body_is_recoverable_as_managed(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7, body="Content")])

        planned = plan.actions[0].payload["body"]
        self.assertEqual("GH-7", extract_item_id(planned))
        self.assertIn("Content", planned)


class ApplyTests(unittest.TestCase):
    class _Service:
        def __init__(self) -> None:
            self.adopted: list[tuple[int, str]] = []

        def adopt_issue(self, number: int, body: str) -> None:
            self.adopted.append((number, body))

    def test_applies_only_the_confirmed_plan(self) -> None:
        data = manifest()
        issues = [_issue(7), _issue(9)]
        plan = build_import_plan(data, issues, include={7})
        service = self._Service()

        result = apply_import_plan(
            plan,
            executor=ImportExecutor(service),
            confirmation=plan.digest,
            manifest=data,
            unmanaged_issues=issues,
        )

        self.assertEqual("completed", result.status)
        self.assertEqual([7], [number for number, _ in service.adopted])

    def test_refuses_without_the_exact_digest(self) -> None:
        data = manifest()
        issues = [_issue(7)]
        plan = build_import_plan(data, issues)

        with self.assertRaises(ApplyAuthorizationError):
            apply_import_plan(
                plan,
                executor=ImportExecutor(self._Service()),
                confirmation="not-the-digest",
                manifest=data,
                unmanaged_issues=issues,
            )

    def test_refuses_when_the_issue_body_changed_after_review(self) -> None:
        data = manifest()
        issues = [_issue(7, body="original")]
        plan = build_import_plan(data, issues)
        drifted = [_issue(7, body="somebody edited this")]

        with self.assertRaisesRegex(ApplyAuthorizationError, "drifted"):
            apply_import_plan(
                plan,
                executor=ImportExecutor(self._Service()),
                confirmation=plan.digest,
                manifest=data,
                unmanaged_issues=drifted,
            )

    def test_a_failure_journals_the_action_with_a_hint(self) -> None:
        class Failing(self._Service):
            def adopt_issue(self, number: int, body: str) -> None:
                raise RuntimeError("boom")

        data = manifest()
        issues = [_issue(7)]
        plan = build_import_plan(data, issues)
        receipts: list = []

        with self.assertRaises(RuntimeError):
            apply_import_plan(
                plan,
                executor=ImportExecutor(Failing()),
                confirmation=plan.digest,
                manifest=data,
                unmanaged_issues=issues,
                journal=receipts.append,
            )

        self.assertEqual("failed", receipts[-1].status)
        self.assertEqual("issue.adopt", receipts[-1].failed_action["kind"])


class IdempotenceTests(unittest.TestCase):
    """R11 - a second import is idempotent."""

    def test_a_second_import_finds_nothing_to_adopt(self) -> None:
        data = manifest()
        issues = [_issue(7), _issue(9)]
        plan = build_import_plan(data, issues)
        merged = merge_imported_items(data, plan.items)

        # After adoption every issue carries the marker, so the reader that
        # supplies unmanaged issues returns none of them.
        adopted_ids = {
            extract_item_id(action.payload["body"]) for action in plan.actions
        }
        self.assertEqual({"GH-7", "GH-9"}, adopted_ids)

        second = build_import_plan(merged, [])

        self.assertEqual([], second.actions)
        self.assertEqual([], second.items)

    def test_the_plan_survives_a_round_trip(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7)])

        restored = import_plan_from_dict(plan.as_dict())

        self.assertEqual(plan.digest, restored.digest)
        self.assertEqual(plan.items, restored.items)

    def test_a_tampered_plan_is_rejected(self) -> None:
        plan = build_import_plan(manifest(), [_issue(7)])
        payload = plan.as_dict()
        payload["items"][0]["impact"] = 5

        with self.assertRaisesRegex(ManifestError, "digest does not match"):
            import_plan_from_dict(payload)


class ProposedIdTests(unittest.TestCase):
    def test_derives_a_stable_id_from_the_issue_number(self) -> None:
        self.assertEqual("GH-42", proposed_item_id(42))


class OrphanRecoveryTests(unittest.TestCase):
    """Adoption marks GitHub before the manifest records it, so that gap must heal."""

    def _marked(self, item_id: str, number: int, **overrides) -> dict:
        issue = _issue(number, **overrides)
        issue["abk_id"] = item_id
        return issue

    def test_finds_a_marker_the_manifest_does_not_know(self) -> None:
        data = manifest(item("T-1"))

        orphans = find_orphans(
            data, [self._marked("T-1", 1), self._marked("GH-63", 63)]
        )

        self.assertEqual(["GH-63"], [issue["abk_id"] for issue in orphans])

    def test_finds_nothing_when_every_marker_is_known(self) -> None:
        data = manifest(item("T-1"))

        self.assertEqual([], find_orphans(data, [self._marked("T-1", 1)]))

    def test_recovers_the_orphan_under_the_id_github_already_uses(self) -> None:
        data = manifest()

        merged, recovered = reconcile_orphans(
            data,
            [self._marked("GH-63", 63, title="Stranded", body="Real content")],
        )

        self.assertEqual(["GH-63"], [entry["id"] for entry in recovered])
        self.assertEqual("Stranded", recovered[0]["title"])
        self.assertEqual("Real content", recovered[0]["description"])
        self.assertIn("GH-63", {entry["id"] for entry in merged["items"]})

    def test_recovery_writes_nothing_when_there_is_nothing_to_recover(self) -> None:
        data = manifest(item("T-1"))

        merged, recovered = reconcile_orphans(data, [self._marked("T-1", 1)])

        self.assertEqual([], recovered)
        self.assertEqual(1, len(merged["items"]))

    def test_recovery_is_idempotent(self) -> None:
        data = manifest()
        marked = [self._marked("GH-63", 63)]

        once, _ = reconcile_orphans(data, marked)
        twice, recovered = reconcile_orphans(once, marked)

        self.assertEqual([], recovered)
        self.assertEqual(
            [entry["id"] for entry in once["items"]],
            [entry["id"] for entry in twice["items"]],
        )

    def test_a_closed_orphan_recovers_as_complete(self) -> None:
        _, recovered = reconcile_orphans(
            manifest(), [self._marked("GH-63", 63, state="closed")]
        )

        self.assertEqual("Done", recovered[0]["status"])


def _related_issue(
    number: int,
    *,
    issue_type: str | None = None,
    parent: dict | None = None,
    blocked_by: list[dict] | None = None,
) -> dict:
    """An unmanaged issue read with `with_relationships=True`."""

    observed = _issue(number, issue_type=issue_type)
    observed["parent_issue"] = parent
    observed["blocked_by"] = blocked_by or []
    return observed


def _related(number: int, abk_id: str | None = None) -> dict:
    return {"number": number, "abk_id": abk_id}


class RelationshipInferenceTests(unittest.TestCase):
    """Issue #63 - adopt the shape GitHub already records, or say why not."""

    def test_relationships_are_not_inferred_unless_asked(self) -> None:
        plan = build_import_plan(
            manifest(),
            [
                _related_issue(7, issue_type="Feature"),
                _related_issue(8, issue_type="Story", parent=_related(7)),
            ],
        )

        self.assertEqual([None, None], [entry["parent"] for entry in plan.items])
        self.assertEqual({}, plan.withheld_relationships)
        self.assertFalse(plan.infer_relationships)

    def test_proposes_a_parent_the_hierarchy_allows(self) -> None:
        plan = build_import_plan(
            manifest(),
            [
                _related_issue(7, issue_type="Feature"),
                _related_issue(8, issue_type="Story", parent=_related(7)),
            ],
            infer_relationships=True,
        )

        self.assertEqual([None, "GH-7"], [entry["parent"] for entry in plan.items])
        self.assertEqual({}, plan.withheld_relationships)
        self.assertTrue(plan.infer_relationships)

    def test_proposes_a_parent_the_manifest_already_manages(self) -> None:
        plan = build_import_plan(
            manifest(item("E-1", item_type="Epic")),
            [_related_issue(8, issue_type="Feature", parent=_related(1, "E-1"))],
            infer_relationships=True,
        )

        self.assertEqual("E-1", plan.items[0]["parent"])

    def test_withholds_a_parent_the_hierarchy_does_not_allow(self) -> None:
        plan = build_import_plan(
            manifest(),
            [
                _related_issue(7, issue_type="Epic"),
                _related_issue(8, issue_type="Story", parent=_related(7)),
            ],
            infer_relationships=True,
        )

        self.assertIsNone(plan.items[1]["parent"])
        self.assertIn(
            "the hierarchy does not allow", plan.withheld_relationships["GH-8"][0]
        )

    def test_withholds_a_parent_that_is_marked_but_unrecorded(self) -> None:
        plan = build_import_plan(
            manifest(),
            [_related_issue(8, issue_type="Story", parent=_related(1, "GH-1"))],
            infer_relationships=True,
        )

        self.assertIsNone(plan.items[0]["parent"])
        self.assertIn("import-reconcile", plan.withheld_relationships["GH-8"][0])

    def test_withholds_a_parent_left_out_of_this_adoption(self) -> None:
        plan = build_import_plan(
            manifest(),
            [
                _related_issue(7, issue_type="Feature"),
                _related_issue(8, issue_type="Story", parent=_related(7)),
            ],
            include={8},
            infer_relationships=True,
        )

        self.assertIsNone(plan.items[0]["parent"])
        self.assertIn(
            "neither managed nor part of this adoption",
            plan.withheld_relationships["GH-8"][0],
        )

    def test_proposes_the_dependencies_github_records(self) -> None:
        plan = build_import_plan(
            manifest(item("T-1")),
            [
                _related_issue(7),
                _related_issue(
                    8, blocked_by=[_related(7), _related(1, "T-1")]
                ),
            ],
            infer_relationships=True,
        )

        self.assertEqual([], plan.items[0]["depends_on"])
        self.assertEqual(["GH-7", "T-1"], plan.items[1]["depends_on"])

    def test_withholds_a_dependency_that_would_close_a_cycle(self) -> None:
        plan = build_import_plan(
            manifest(),
            [
                _related_issue(7, blocked_by=[_related(8)]),
                _related_issue(8, blocked_by=[_related(7)]),
            ],
            infer_relationships=True,
        )

        self.assertEqual(["GH-8"], plan.items[0]["depends_on"])
        self.assertEqual([], plan.items[1]["depends_on"])
        self.assertIn(
            "would close a dependency cycle", plan.withheld_relationships["GH-8"][0]
        )

    def test_refuses_to_infer_from_issues_read_without_relationships(self) -> None:
        with self.assertRaisesRegex(ManifestError, r"#9"):
            build_import_plan(
                manifest(),
                [_related_issue(7), _issue(9)],
                infer_relationships=True,
            )

    def test_an_inferred_plan_round_trips_through_its_serialized_form(self) -> None:
        plan = build_import_plan(
            manifest(),
            [
                _related_issue(7, issue_type="Epic"),
                _related_issue(8, issue_type="Story", parent=_related(7)),
            ],
            infer_relationships=True,
        )

        restored = import_plan_from_dict(plan.as_dict())

        self.assertTrue(restored.infer_relationships)
        self.assertEqual(plan.withheld_relationships, restored.withheld_relationships)
        self.assertEqual(plan.digest, restored.digest)

    def test_apply_rebuilds_the_plan_the_same_way_it_was_reviewed(self) -> None:
        issues = [
            _related_issue(7, issue_type="Feature"),
            _related_issue(8, issue_type="Story", parent=_related(7)),
        ]
        plan = build_import_plan(manifest(), issues, infer_relationships=True)
        adopted: list[str] = []

        apply_import_plan(
            plan,
            executor=lambda action: adopted.append(action.item_id),
            confirmation=plan.digest,
            manifest=manifest(),
            unmanaged_issues=issues,
        )

        self.assertEqual(["GH-7", "GH-8"], adopted)

    def test_apply_refuses_a_plan_whose_inference_flag_was_edited(self) -> None:
        issues = [
            _related_issue(7, issue_type="Feature"),
            _related_issue(8, issue_type="Story", parent=_related(7)),
        ]
        plan = build_import_plan(manifest(), issues, infer_relationships=True)
        tampered = import_plan_from_dict(
            {**plan.as_dict(), "infer_relationships": False}
        )

        with self.assertRaises(ApplyAuthorizationError):
            apply_import_plan(
                tampered,
                executor=lambda action: None,
                confirmation=plan.digest,
                manifest=manifest(),
                unmanaged_issues=issues,
            )


if __name__ == "__main__":
    unittest.main()
