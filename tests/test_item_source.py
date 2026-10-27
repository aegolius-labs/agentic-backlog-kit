"""Q06-F02: an optional, unique `source` keeps a repeated handoff from becoming a second item."""

from __future__ import annotations

import unittest

from agentic_backlog_kit.manifest import ManifestError, validate_manifest
from agentic_backlog_kit.mutations import add_item, update_item
from agentic_backlog_kit.sync import render_issue_body

from tests.helpers import item, manifest


SOURCE = "agentic-qa-kit:session=q01-fixture;finding=F-001"


def _draft(source: str | None = SOURCE) -> dict:
    draft = item("placeholder", title="Rounding is wrong")
    draft.pop("id")
    if source is not None:
        draft["source"] = source
    return draft


class ItemSourceTests(unittest.TestCase):
    def test_source_is_optional_and_kept_as_written(self) -> None:
        updated, item_id = add_item(manifest(), _draft())

        stored = next(entry for entry in updated["items"] if entry["id"] == item_id)
        self.assertEqual(SOURCE, stored["source"])
        self.assertNotIn("source", validate_manifest(manifest(item("T-1")))["items"][0])

    def test_null_source_means_absent(self) -> None:
        data = manifest(dict(item("T-1"), source=None))

        self.assertNotIn("source", validate_manifest(data)["items"][0])

    def test_a_repeated_handoff_is_refused(self) -> None:
        once, first = add_item(manifest(), _draft())

        with self.assertRaisesRegex(ManifestError, f"'{first}' and .* carry the same source"):
            add_item(once, _draft())

    def test_different_sources_coexist(self) -> None:
        once, _ = add_item(manifest(), _draft())
        twice, _ = add_item(once, _draft(SOURCE.replace("F-001", "F-002")))

        self.assertEqual(2, len(twice["items"]))

    def test_source_must_be_a_bounded_nonempty_string(self) -> None:
        for bad in ("", "   ", 7, ["x"], "x" * 257):
            with self.subTest(source=bad), self.assertRaises(ManifestError):
                validate_manifest(manifest(dict(item("T-1"), source=bad)))

    def test_update_cannot_change_source(self) -> None:
        data, item_id = add_item(manifest(), _draft())

        with self.assertRaisesRegex(ManifestError, "unknown fields"):
            update_item(data, item_id, {"source": "other"})

    def test_source_is_not_projected_into_the_issue_body(self) -> None:
        data, item_id = add_item(manifest(), _draft())
        stored = next(entry for entry in data["items"] if entry["id"] == item_id)

        self.assertNotIn(SOURCE, render_issue_body(stored))


if __name__ == "__main__":
    unittest.main()
