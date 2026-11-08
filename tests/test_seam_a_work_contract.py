"""Seam A forward contract: aio-agentic-sdlc work arrives as a valid manifest.

`aio-agentic-sdlc` exports the work its drift triage authorizes with
`dag-tool export-abk`. `tests/fixtures/seam-a/work.json` is byte-identical to
that repository's copy, whose test produces `manifest` from `base_manifest`.
This side proves the kit accepts the result with its own engine, without
importing the framework.

If this test fails, the seam moved. Update both fixtures together and say so
in the change; do not quietly relax the assertion.
"""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from agentic_backlog_kit.manifest import validate_manifest
from agentic_backlog_kit.priority import prioritize
from agentic_backlog_kit.sync import build_sync_plan, extract_guid, render_issue_body


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "seam-a" / "work.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class SeamAWorkContractTests(unittest.TestCase):
    def test_contract_identity(self) -> None:
        fixture = _fixture()

        self.assertEqual("seam-a-work", fixture["contract"])
        self.assertEqual(1, fixture["contract_version"])

    def test_base_and_exported_manifests_are_valid(self) -> None:
        fixture = _fixture()

        validate_manifest(deepcopy(fixture["base_manifest"]))
        normalized = validate_manifest(deepcopy(fixture["manifest"]))

        self.assertEqual(2, normalized["schema_version"])

    def test_items_without_a_guid_pass_through_unchanged(self) -> None:
        fixture = _fixture()
        manual = [i for i in fixture["manifest"]["items"] if not i.get("guid")]

        self.assertEqual(fixture["base_manifest"]["items"], manual)

    def test_exported_items_carry_their_guid_into_the_issue_marker(self) -> None:
        fixture = _fixture()
        exported = [i for i in fixture["manifest"]["items"] if i.get("guid")]

        self.assertTrue(exported)
        for item in exported:
            self.assertEqual("Task", item["type"])
            self.assertTrue(item["id"].startswith("SDLC-"))
            self.assertEqual(item["guid"], extract_guid(render_issue_body(item)))

    def test_exported_work_prioritizes_and_plans_against_an_empty_project(self) -> None:
        manifest = validate_manifest(deepcopy(_fixture()["manifest"]))

        ranked = prioritize(manifest)
        plan = build_sync_plan(manifest, {"issues": []})

        self.assertTrue(ranked)
        planned = {action.item_id for action in plan.actions}
        self.assertEqual({item["id"] for item in manifest["items"]}, planned)


if __name__ == "__main__":
    unittest.main()
