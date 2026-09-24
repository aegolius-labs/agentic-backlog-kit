"""R25: carry an optional canonical GUID from the manifest into the issue marker."""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from agentic_backlog_kit.github import GitHubCliTransport
from agentic_backlog_kit.importing import reconcile_orphans
from agentic_backlog_kit.manifest import (
    SCHEMA_VERSION,
    ManifestError,
    canonical_guid,
    validate_manifest,
)
from agentic_backlog_kit.snapshot import GitHubSnapshotReader
from agentic_backlog_kit.sync import (
    build_sync_plan,
    extract_guid,
    extract_item_id,
    render_issue_body,
    render_marker,
)

from tests.helpers import item, manifest


ROOT = Path(__file__).resolve().parents[1]
GUID = "123e4567-e89b-12d3-a456-426614174000"
OTHER_GUID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
LEGACY_MARKER = "<!-- agentic-backlog-kit:id=T-1;schema=1 -->"
GUID_MARKER = f"<!-- agentic-backlog-kit:id=T-1;schema=1;guid={GUID} -->"
NON_CANONICAL = [
    GUID.upper(),
    "{" + GUID + "}",
    "urn:uuid:" + GUID,
    GUID.replace("-", ""),
    "not-a-guid",
    "",
    42,
    True,
]


def _v2(*items: dict) -> dict:
    data = manifest(*items)
    data["schema_version"] = 2
    return data


def _with_guid(item_id: str, guid: str | None = GUID, **overrides) -> dict:
    value = item(item_id, **overrides)
    value["guid"] = guid
    return value


def _remote(item_id: str, body: str, *, number: int = 1) -> dict:
    return {
        "abk_id": item_id,
        "number": number,
        "title": item_id,
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


class GuidValidationTests(unittest.TestCase):
    def test_a_canonical_guid_is_accepted_and_kept(self) -> None:
        normalized = validate_manifest(_v2(_with_guid("T-1")))

        self.assertEqual(GUID, normalized["items"][0]["guid"])

    def test_an_item_without_a_guid_stays_valid_and_gains_no_key(self) -> None:
        normalized = validate_manifest(_v2(item("T-1")))

        self.assertNotIn("guid", normalized["items"][0])

    def test_a_null_guid_is_the_same_as_none(self) -> None:
        normalized = validate_manifest(_v2(_with_guid("T-1", None)))

        self.assertNotIn("guid", normalized["items"][0])

    def test_every_non_canonical_spelling_is_rejected_before_planning(self) -> None:
        for value in NON_CANONICAL:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ManifestError, "canonical lowercase UUID"):
                    validate_manifest(_v2(_with_guid("T-1", value)))

    def test_two_items_cannot_claim_one_guid(self) -> None:
        with self.assertRaisesRegex(ManifestError, "same guid"):
            validate_manifest(_v2(_with_guid("T-1"), _with_guid("T-2")))

    def test_schema_pattern_agrees_with_the_engine(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8")
        )
        guid_schema = schema["$defs"]["item"]["properties"]["guid"]["oneOf"][0]
        pattern = re.compile(guid_schema["pattern"])

        for value in [GUID, OTHER_GUID, *NON_CANONICAL]:
            with self.subTest(value=value):
                engine = canonical_guid(value) is not None
                schema_accepts = isinstance(value, str) and bool(pattern.fullmatch(value))
                self.assertEqual(engine, schema_accepts)


class SchemaMigrationTests(unittest.TestCase):
    def test_version_one_loads_and_is_written_back_as_version_two(self) -> None:
        data = manifest(item("T-1"))
        self.assertEqual(1, data["schema_version"])

        normalized = validate_manifest(data)

        self.assertEqual(SCHEMA_VERSION, normalized["schema_version"])
        self.assertEqual(2, normalized["schema_version"])
        self.assertEqual(
            validate_manifest(_v2(item("T-1")))["items"], normalized["items"]
        )

    def test_migration_is_stable_once_applied(self) -> None:
        once = validate_manifest(manifest(item("T-1")))

        self.assertEqual(once, validate_manifest(once))

    def test_version_one_cannot_carry_a_guid(self) -> None:
        data = manifest(_with_guid("T-1"))

        with self.assertRaisesRegex(ManifestError, "schema_version 1 cannot"):
            validate_manifest(data)

    def test_unknown_versions_are_rejected(self) -> None:
        for version in (0, 3, "2", True, None):
            with self.subTest(version=version):
                data = manifest(item("T-1"))
                data["schema_version"] = version
                with self.assertRaisesRegex(ManifestError, "schema_version must be one of"):
                    validate_manifest(data)

    def test_bundled_manifests_are_current(self) -> None:
        for relative in ("templates/manifest.json", "examples/manifest.json"):
            with self.subTest(path=relative):
                data = json.loads((ROOT / relative).read_text(encoding="utf-8"))
                self.assertEqual(SCHEMA_VERSION, data["schema_version"])
                validate_manifest(data)


class MarkerTests(unittest.TestCase):
    def test_an_item_without_a_guid_keeps_the_legacy_marker_exactly(self) -> None:
        self.assertEqual(LEGACY_MARKER, render_marker(item("T-1")))
        self.assertTrue(render_issue_body(item("T-1")).startswith(LEGACY_MARKER + "\n"))

    def test_a_guid_is_appended_after_the_marker_schema(self) -> None:
        self.assertEqual(GUID_MARKER, render_marker(_with_guid("T-1")))

    def test_a_reader_that_stops_at_the_first_separator_still_finds_the_id(self) -> None:
        # Every released kit reads the id this way, which is why the marker
        # schema did not have to change.
        legacy_reader = GUID_MARKER.split("agentic-backlog-kit:id=", 1)[1].split(";", 1)[0]

        self.assertEqual("T-1", legacy_reader)
        self.assertEqual("T-1", extract_item_id(GUID_MARKER))

    def test_the_guid_reads_back_from_anywhere_in_the_body(self) -> None:
        self.assertEqual(GUID, extract_guid(f"Intro\n\n{GUID_MARKER}\n\nMore"))

    def test_absent_or_non_canonical_marker_guids_read_as_none(self) -> None:
        self.assertIsNone(extract_guid(LEGACY_MARKER))
        self.assertIsNone(extract_guid("no marker at all"))
        self.assertIsNone(extract_guid(None))
        self.assertIsNone(
            extract_guid(GUID_MARKER.replace(GUID, GUID.upper()))
        )


class GuidSyncTests(unittest.TestCase):
    def test_a_guid_added_to_the_manifest_is_written_into_the_body(self) -> None:
        local = _with_guid("T-1")
        remote = _remote("T-1", render_issue_body(item("T-1")))

        plan = build_sync_plan(_v2(local), {"issues": [remote]})

        update = next(action for action in plan.actions if action.kind == "issue.update")
        self.assertEqual(render_issue_body(local), update.payload["body"])
        self.assertIn(GUID_MARKER, update.payload["body"])

    def test_existing_issues_without_a_guid_are_not_rewritten(self) -> None:
        local = item("T-1")
        remote = _remote("T-1", render_issue_body(local))

        plan = build_sync_plan(_v2(local), {"issues": [remote]})

        self.assertEqual([], [a for a in plan.actions if a.kind == "issue.update"])

    def test_a_preserved_body_has_only_its_marker_corrected(self) -> None:
        local = _with_guid("T-1")
        body = f"Written by a person.\n\n{LEGACY_MARKER}\n\n- keep this list"
        remote = _remote("T-1", body)

        plan = build_sync_plan(_v2(local), {"issues": [remote]}, manage_body=False)

        update = next(action for action in plan.actions if action.kind == "issue.update")
        self.assertEqual(
            f"Written by a person.\n\n{GUID_MARKER}\n\n- keep this list",
            update.payload["body"],
        )

    def test_a_preserved_body_with_the_right_guid_is_left_alone(self) -> None:
        local = _with_guid("T-1")
        remote = _remote("T-1", f"Anything at all.\n\n{GUID_MARKER}")

        plan = build_sync_plan(_v2(local), {"issues": [remote]}, manage_body=False)

        self.assertEqual([], [a for a in plan.actions if a.kind == "issue.update"])

    def test_a_changed_guid_is_corrected_rather_than_kept(self) -> None:
        local = _with_guid("T-1", OTHER_GUID)
        remote = _remote("T-1", f"Prose.\n\n{GUID_MARKER}")

        plan = build_sync_plan(_v2(local), {"issues": [remote]}, manage_body=False)

        update = next(action for action in plan.actions if action.kind == "issue.update")
        self.assertEqual(OTHER_GUID, extract_guid(update.payload["body"]))
        self.assertTrue(update.payload["body"].startswith("Prose.\n\n"))

    def test_the_second_plan_after_writing_the_guid_is_empty(self) -> None:
        local = _with_guid("T-1")
        remote = _remote("T-1", render_issue_body(local))

        plan = build_sync_plan(_v2(local), {"issues": [remote]})

        self.assertEqual([], plan.actions)


class GuidReadAndRecoveryTests(unittest.TestCase):
    def _read(self, body: str) -> dict:
        issues_path = "repos/aegolius-labs/example/issues?state=all&per_page=100&page=1"
        parent_path = "repos/aegolius-labs/example/issues/1/parent"
        dependencies_path = (
            "repos/aegolius-labs/example/issues/1/dependencies/blocked_by?per_page=100"
        )
        issue = {
            "id": 101,
            "node_id": "NODE_1",
            "number": 1,
            "html_url": "issue-1",
            "title": "T-1",
            "body": body,
            "state": "open",
            "type": {"name": "Task"},
            "labels": [],
        }
        project = {
            "organization": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        def run(command, **kwargs):
            path = command[4]
            if path == issues_path:
                return subprocess.CompletedProcess(command, 0, json.dumps([issue]), "")
            if path == parent_path:
                return subprocess.CompletedProcess(
                    command, 1, "", "gh: No parent issue found (HTTP 404)"
                )
            if path == dependencies_path:
                return subprocess.CompletedProcess(command, 0, "[]", "")
            if path == "graphql":
                return subprocess.CompletedProcess(
                    command, 0, json.dumps({"data": project}), ""
                )
            raise AssertionError(f"unexpected gh path: {path}")

        with patch("agentic_backlog_kit.github.subprocess.run", side_effect=run):
            snapshot = GitHubSnapshotReader(
                GitHubCliTransport("gh"),
                owner="aegolius-labs",
                repository="example",
                project_number=1,
            ).read()
        return snapshot["issues"][0]

    def test_snapshot_reports_the_marker_guid(self) -> None:
        read = self._read(GUID_MARKER)

        self.assertEqual("T-1", read["abk_id"])
        self.assertEqual(GUID, read["guid"])

    def test_snapshot_of_a_legacy_marker_has_no_guid_key(self) -> None:
        self.assertNotIn("guid", self._read(LEGACY_MARKER))

    def test_orphan_recovery_keeps_the_guid_the_marker_carries(self) -> None:
        orphan = {
            "abk_id": "T-1",
            "number": 1,
            "node_id": "I_1",
            "title": "Stranded",
            "body": f"{GUID_MARKER}\n\nReal content",
            "state": "open",
            "labels": [],
            "type": None,
        }

        merged, recovered, _ = reconcile_orphans(manifest(), [orphan])

        self.assertEqual(GUID, recovered[0]["guid"])
        self.assertEqual(2, merged["schema_version"])
        self.assertEqual(GUID, merged["items"][0]["guid"])
        self.assertEqual("Real content", recovered[0]["description"])

    def test_orphan_recovery_without_a_guid_adds_none(self) -> None:
        orphan = {
            "abk_id": "T-1",
            "number": 1,
            "node_id": "I_1",
            "title": "Stranded",
            "body": f"{LEGACY_MARKER}\n\nReal content",
            "state": "open",
            "labels": [],
            "type": None,
        }

        _, recovered, _ = reconcile_orphans(manifest(), [orphan])

        self.assertNotIn("guid", recovered[0])


if __name__ == "__main__":
    unittest.main()
