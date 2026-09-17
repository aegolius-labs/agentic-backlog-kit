"""Seam B contract: an Agentic QA Kit handoff payload must be ingestible here.

`agentic-qa-kit` emits a confirmed defect as one `Bug` payload for this kit to
ingest. The two repositories are independently installable and must not import
each other, so the contract is pinned by a committed fixture on each side.
`tests/fixtures/qa-handoff/bug-payload.json` is a real, unedited
`qa.py backlog-export` result. The matching test in `agentic-qa-kit` asserts its
exporter still produces this shape.

If this test fails, the seam moved. Fix the adapter or update both fixtures
together and say so in the change; do not quietly relax the assertion.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agentic_backlog_kit.manifest import ManifestError, validate_manifest

from tests import helpers


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "tests" / "fixtures" / "qa-handoff" / "bug-payload.json"

# Every field a manifest item requires. The QA kit supplies all of them except
# `id`, which this kit owns and generates on ingestion.
ITEM_FIELDS = {
    "id",
    "title",
    "type",
    "description",
    "acceptance_criteria",
    "parent",
    "depends_on",
    "impact",
    "effort",
    "business_value",
    "enabler_value",
    "status",
    "maturity",
    "sprint",
}
QA_SUPPLIED_FIELDS = ITEM_FIELDS - {"id"}


def _payload() -> dict:
    return json.loads(PAYLOAD.read_text(encoding="utf-8"))


class QaHandoffContractTests(unittest.TestCase):
    def test_payload_supplies_exactly_the_fields_this_kit_expects(self) -> None:
        payload = _payload()

        self.assertEqual(
            QA_SUPPLIED_FIELDS,
            set(payload),
            "QA handoff payload no longer matches the manifest item field set",
        )
        self.assertNotIn(
            "id", payload, "the QA kit must not assign backlog IDs; this kit owns them"
        )

    def test_payload_is_ingestible_as_a_bug(self) -> None:
        payload = _payload()
        self.assertEqual("Bug", payload["type"], "handoff payloads are always Bugs")

        ingested = dict(payload, id="ABK-1")
        validated = validate_manifest(helpers.manifest(ingested))

        stored = next(i for i in validated["items"] if i["id"] == "ABK-1")
        self.assertEqual(payload["title"], stored["title"])
        self.assertEqual(payload["acceptance_criteria"], stored["acceptance_criteria"])
        for field in ("impact", "effort", "business_value", "enabler_value"):
            self.assertEqual(payload[field], stored[field])

    def test_payload_preserves_qa_traceability(self) -> None:
        description = _payload()["description"]

        # The QA session and finding IDs and the exact target revision must
        # survive into the backlog item, or a projected issue cannot be traced
        # back to the evidence that justified it.
        self.assertIn("QA session:", description)
        self.assertIn("QA finding:", description)
        self.assertIn("Target revision:", description)
        self.assertIn("Evidence:", description)
        self.assertIn("Limitations:", description)

    def test_a_handoff_missing_planning_inputs_is_rejected(self) -> None:
        incomplete = dict(_payload(), id="ABK-1")
        del incomplete["impact"]

        with self.assertRaises(ManifestError):
            validate_manifest(helpers.manifest(incomplete))

    def test_qa_severity_is_not_treated_as_backlog_priority(self) -> None:
        payload = _payload()

        # QA severity lives in the description as evidence. It must never be
        # mapped onto a planning score, which is an owner decision made here.
        self.assertIn("QA severity:", payload["description"])
        self.assertNotIn("severity", payload)


if __name__ == "__main__":
    unittest.main()
