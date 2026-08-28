from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agentic_backlog_kit.manifest import ManifestError
from agentic_backlog_kit.mutations import (
    StaleManifestError,
    add_item,
    file_sha256,
    save_manifest,
    update_item,
)

from tests.helpers import item, manifest


class ManifestMutationTests(unittest.TestCase):
    def test_add_generates_a_stable_type_prefixed_id(self) -> None:
        data = manifest(item("TASK-0001"))
        draft = item("placeholder", title="Second")
        draft.pop("id")

        updated, item_id = add_item(data, draft)

        self.assertEqual("TASK-0002", item_id)
        self.assertIn(item_id, {entry["id"] for entry in updated["items"]})

    def test_update_is_a_patch_and_preserves_other_fields(self) -> None:
        data = manifest(item("TASK-0001", title="Before", impact=2))

        updated = update_item(data, "TASK-0001", {"title": "After"})
        changed = updated["items"][0]

        self.assertEqual("After", changed["title"])
        self.assertEqual(2, changed["impact"])

    def test_update_cannot_change_identity(self) -> None:
        with self.assertRaisesRegex(ManifestError, "cannot change id"):
            update_item(manifest(item("TASK-0001")), "TASK-0001", {"id": "OTHER"})

    def test_save_rejects_a_stale_expected_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest()), encoding="utf-8")

            with self.assertRaises(StaleManifestError):
                save_manifest(path, manifest(), expected_sha256="0" * 64)

    def test_save_replaces_the_expected_version_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest()), encoding="utf-8")
            expected = file_sha256(path)
            updated, _ = add_item(manifest(), {**item("TASK-0001")})

            result_hash = save_manifest(path, updated, expected_sha256=expected)

            self.assertEqual(result_hash, file_sha256(path))
            self.assertEqual(1, len(json.loads(path.read_text(encoding="utf-8"))["items"]))


if __name__ == "__main__":
    unittest.main()
