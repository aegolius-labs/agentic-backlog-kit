"""Seam A contract: a canonical GUID survives from the Intention DAG to GitHub.

`aio-agentic-sdlc` owns canonical GUID traceability and projects accepted work
into this kit. The two repositories are independently installable and must not
import each other, so the identity half of the contract is pinned by a committed
fixture on each side. `tests/fixtures/seam-a/projected-item.json` holds one
projected manifest item and the marker this kit writes for it; the matching test
in `aio-agentic-sdlc` asserts the same GUID passes its own canonical check and
reaches the marker unchanged.

If this test fails, the seam moved. Fix the carrier or update both fixtures
together and say so in the change; do not quietly relax the assertion.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agentic_backlog_kit.manifest import SCHEMA_VERSION, canonical_guid, validate_manifest
from agentic_backlog_kit.sync import (
    extract_guid,
    extract_item_id,
    render_issue_body,
    render_marker,
)

from tests import helpers


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "seam-a" / "projected-item.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class SeamAContractTests(unittest.TestCase):
    def test_fixture_guid_is_canonical_and_carried_by_the_item(self) -> None:
        fixture = _fixture()

        self.assertEqual(fixture["guid"], canonical_guid(fixture["guid"]))
        self.assertEqual(fixture["guid"], fixture["item"]["guid"])

    def test_projected_item_is_valid_in_a_current_manifest(self) -> None:
        fixture = _fixture()
        data = helpers.manifest(fixture["item"])
        data["schema_version"] = SCHEMA_VERSION

        normalized = validate_manifest(data)

        self.assertEqual(fixture["guid"], normalized["items"][0]["guid"])

    def test_the_kit_writes_exactly_the_pinned_marker(self) -> None:
        fixture = _fixture()

        self.assertEqual(fixture["marker"], render_marker(fixture["item"]))
        self.assertTrue(
            render_issue_body(fixture["item"]).startswith(fixture["marker"] + "\n")
        )

    def test_the_pinned_marker_reads_back_to_the_same_identity(self) -> None:
        fixture = _fixture()
        body = f"Human prose above.\n\n{fixture['marker']}\n\nAnd below."

        self.assertEqual(fixture["item"]["id"], extract_item_id(body))
        self.assertEqual(fixture["guid"], extract_guid(body))


if __name__ == "__main__":
    unittest.main()
