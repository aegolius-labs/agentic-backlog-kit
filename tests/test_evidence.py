"""S-R35-3: observed-state evidence export.

`agentic_backlog_kit.evidence.observed_state` renders GitHub's currently
observed state for issues this kit manages as a small, versioned contract -
evidence for a downstream system (`aio-agentic-sdlc`'s Reality DAG), never an
edit to intent. `tests/fixtures/seam-a/observed-state.json` pins that contract
so a counterpart repository can copy it; this file both regenerates that exact
fixture from a synthetic manifest/snapshot and exercises the function's rules
directly (nulls, digest stability, additive omission of url/closed_at).
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from agentic_backlog_kit import __version__
from agentic_backlog_kit.evidence import CONTRACT, CONTRACT_VERSION, observed_state
from agentic_backlog_kit.execution import state_fingerprint

from tests.helpers import item, manifest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "seam-a" / "observed-state.json"
SCHEMA = ROOT / "schemas" / "observed-state.schema.json"

GUID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


def _seam_a_manifest() -> dict:
    data = manifest(
        item(
            "F-SEAM-A",
            title="Project one Intention DAG node onto GitHub",
            item_type="Feature",
            impact=3,
            effort=3,
            business_value=3,
            enabler_value=2,
        )
    )
    data["schema_version"] = 2
    data["items"][0]["guid"] = GUID
    data["workflow"]["iteration"] = {
        "field": "Sprint",
        "start_date": "2026-09-21",
        "duration_days": 14,
    }
    data["workflow"]["work_item_types"] = ["Story", "Bug", "Task", "Feature"]
    return data


def _seam_a_snapshot(*, unmanaged_issue_count: int = 2) -> dict:
    return {
        "schema_version": 1,
        "github": {
            "owner": "aegolius-labs",
            "repository": "example",
            "project_number": 1,
        },
        "issues": [
            {
                "abk_id": "F-SEAM-A",
                "number": 42,
                "id": 900042,
                "node_id": "ISSUE_F_SEAM_A",
                "url": "https://github.com/aegolius-labs/example/issues/42",
                "title": "Project one Intention DAG node onto GitHub",
                "body": (
                    "<!-- agentic-backlog-kit:id=F-SEAM-A;schema=1;"
                    f"guid={GUID} -->"
                ),
                "type": "Feature",
                "labels": [],
                "state": "open",
                "in_project": True,
                "project_item_id": "PVTI_1",
                "project_fields": {
                    "Status": "Ready",
                    "Sprint": "Sprint 4",
                    "Impact": 3,
                    "Effort": 3,
                    "Business Value": 3,
                    "Enabler Value": 2,
                    "Priority": 14.0,
                },
                "parent_abk_id": None,
                "depends_on_abk_ids": [],
                "guid": GUID,
            }
        ],
        "unmanaged_issue_count": unmanaged_issue_count,
    }


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class PinnedFixtureTests(unittest.TestCase):
    """The fixture is a contract a counterpart repository can copy verbatim."""

    def test_regenerating_from_the_synthetic_snapshot_matches_the_fixture(self) -> None:
        fixture = _fixture()

        document = observed_state(
            _seam_a_manifest(),
            _seam_a_snapshot(),
            "2026-09-28T12:00:00Z",
            "gh",
        )

        self.assertEqual(fixture, document)

    def test_the_fixture_carries_the_current_package_version(self) -> None:
        # A version bump must regenerate this fixture deliberately, not drift
        # silently: this test fails loudly the moment the two disagree.
        self.assertEqual(__version__, _fixture()["source"]["version"])

    def test_the_fixture_reuses_the_seam_a_identity(self) -> None:
        fixture = _fixture()
        self.assertEqual("F-SEAM-A", fixture["items"][0]["item_id"])
        self.assertEqual(GUID, fixture["items"][0]["guid"])


class ObservedStateShapeTests(unittest.TestCase):
    def test_contract_name_and_version(self) -> None:
        document = observed_state(_seam_a_manifest(), _seam_a_snapshot(), "2026-01-01T00:00:00Z", "gh")

        self.assertEqual(CONTRACT, document["contract"])
        self.assertEqual(CONTRACT_VERSION, document["contract_version"])
        self.assertEqual("abk-observed-state", document["contract"])
        self.assertEqual(1, document["contract_version"])

    def test_items_are_sorted_by_item_id(self) -> None:
        data = manifest(item("T-2"), item("T-1"))
        snapshot = {
            "issues": [
                {"abk_id": "T-2", "number": 2, "state": "open", "in_project": False},
                {"abk_id": "T-1", "number": 1, "state": "open", "in_project": False},
            ]
        }

        document = observed_state(data, snapshot, "2026-01-01T00:00:00Z", "gh")

        self.assertEqual(
            ["T-1", "T-2"], [entry["item_id"] for entry in document["items"]]
        )

    def test_status_and_sprint_are_null_when_not_in_the_project(self) -> None:
        data = manifest(item("T-1"))
        snapshot = {
            "issues": [
                {
                    "abk_id": "T-1",
                    "number": 1,
                    "state": "open",
                    "in_project": False,
                    "project_fields": {"Status": "Ready"},
                }
            ]
        }

        document = observed_state(data, snapshot, "2026-01-01T00:00:00Z", "gh")

        entry = document["items"][0]
        self.assertFalse(entry["in_project"])
        self.assertIsNone(entry["status"])
        self.assertIsNone(entry["sprint"])

    def test_guid_falls_back_to_extracting_it_from_the_body(self) -> None:
        data = manifest(item("T-1"))
        snapshot = {
            "issues": [
                {
                    "abk_id": "T-1",
                    "number": 1,
                    "state": "open",
                    "in_project": False,
                    "body": f"<!-- agentic-backlog-kit:id=T-1;schema=1;guid={GUID} -->",
                }
            ]
        }

        document = observed_state(data, snapshot, "2026-01-01T00:00:00Z", "gh")

        self.assertEqual(GUID, document["items"][0]["guid"])

    def test_guid_is_null_when_absent_entirely(self) -> None:
        data = manifest(item("T-1"))
        snapshot = {
            "issues": [{"abk_id": "T-1", "number": 1, "state": "open", "in_project": False}]
        }

        document = observed_state(data, snapshot, "2026-01-01T00:00:00Z", "gh")

        self.assertIsNone(document["items"][0]["guid"])

    def test_in_manifest_reflects_the_manifests_own_items(self) -> None:
        data = manifest(item("T-1"))
        snapshot = {
            "issues": [
                {"abk_id": "T-1", "number": 1, "state": "open", "in_project": False},
                {"abk_id": "T-9", "number": 9, "state": "open", "in_project": False},
            ]
        }

        document = observed_state(data, snapshot, "2026-01-01T00:00:00Z", "gh")

        by_id = {entry["item_id"]: entry for entry in document["items"]}
        self.assertTrue(by_id["T-1"]["in_manifest"])
        self.assertFalse(by_id["T-9"]["in_manifest"])

    def test_url_and_closed_at_are_omitted_rather_than_fabricated(self) -> None:
        data = manifest(item("T-1"))
        snapshot = {
            "issues": [{"abk_id": "T-1", "number": 1, "state": "closed", "in_project": False}]
        }

        document = observed_state(data, snapshot, "2026-01-01T00:00:00Z", "gh")

        entry = document["items"][0]
        self.assertNotIn("url", entry)
        self.assertNotIn("closed_at", entry)

    def test_unmanaged_issue_count_defaults_to_zero_when_the_snapshot_omits_it(
        self,
    ) -> None:
        data = manifest(item("T-1"))
        snapshot = {"issues": []}

        document = observed_state(data, snapshot, "2026-01-01T00:00:00Z", "gh")

        self.assertEqual(0, document["unmanaged_issue_count"])

    def test_digest_covers_everything_but_itself(self) -> None:
        document = observed_state(_seam_a_manifest(), _seam_a_snapshot(), "2026-01-01T00:00:00Z", "gh")

        without_digest = {key: value for key, value in document.items() if key != "digest"}
        expected = f"sha256:{state_fingerprint(without_digest)}"

        self.assertEqual(expected, document["digest"])

    def test_digest_changes_when_an_observed_field_changes(self) -> None:
        first = observed_state(_seam_a_manifest(), _seam_a_snapshot(), "2026-01-01T00:00:00Z", "gh")
        second = observed_state(
            _seam_a_manifest(), _seam_a_snapshot(unmanaged_issue_count=3), "2026-01-01T00:00:00Z", "gh"
        )

        self.assertNotEqual(first["digest"], second["digest"])

    def test_additive_field_keeps_the_contract_version(self) -> None:
        # Documents the versioning rule the schema and docs both state: an
        # additive field (like a new optional item key) must not require a
        # contract_version bump. This guards against a future change silently
        # coupling the two.
        document = observed_state(_seam_a_manifest(), _seam_a_snapshot(), "2026-01-01T00:00:00Z", "gh")
        self.assertEqual(1, document["contract_version"])


class SchemaShapeTests(unittest.TestCase):
    """Stdlib-only structural checks against the committed JSON Schema.

    No `jsonschema` dependency is available (the kit is dependency-free), so
    this spot-checks the schema's own declared shape - required keys, enums,
    and patterns - the same way `tests/test_canonical_guid.py` cross-checks
    the manifest schema's guid pattern against the engine.
    """

    @staticmethod
    def _schema() -> dict:
        return json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_schema_declares_the_pinned_contract_name_and_version(self) -> None:
        schema = self._schema()
        self.assertEqual(
            "abk-observed-state", schema["properties"]["contract"]["const"]
        )
        self.assertEqual(1, schema["properties"]["contract_version"]["minimum"])

    def test_fixture_satisfies_every_top_level_required_key(self) -> None:
        schema = self._schema()
        fixture = _fixture()
        for key in schema["required"]:
            with self.subTest(key=key):
                self.assertIn(key, fixture)
        self.assertEqual(set(schema["properties"]), set(fixture))

    def test_fixture_item_satisfies_every_required_item_key(self) -> None:
        schema = self._schema()
        item_schema = schema["$defs"]["item"]
        entry = _fixture()["items"][0]
        for key in item_schema["required"]:
            with self.subTest(key=key):
                self.assertIn(key, entry)
        self.assertTrue(set(entry).issubset(set(item_schema["properties"])))

    def test_fixture_digest_matches_the_schema_pattern(self) -> None:
        schema = self._schema()
        pattern = re.compile(schema["properties"]["digest"]["pattern"])
        self.assertTrue(pattern.fullmatch(_fixture()["digest"]))

    def test_fixture_observed_at_matches_the_schema_pattern(self) -> None:
        schema = self._schema()
        pattern = re.compile(schema["properties"]["observed_at"]["pattern"])
        self.assertTrue(pattern.fullmatch(_fixture()["observed_at"]))

    def test_fixture_state_is_one_of_the_schema_enum(self) -> None:
        schema = self._schema()
        allowed = schema["$defs"]["item"]["properties"]["state"]["enum"]
        self.assertIn(_fixture()["items"][0]["state"], allowed)

    def test_fixture_guid_matches_the_schema_pattern(self) -> None:
        schema = self._schema()
        pattern = re.compile(
            schema["$defs"]["item"]["properties"]["guid"]["oneOf"][0]["pattern"]
        )
        self.assertTrue(pattern.fullmatch(_fixture()["items"][0]["guid"]))


if __name__ == "__main__":
    unittest.main()
