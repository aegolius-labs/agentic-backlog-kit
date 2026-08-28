from __future__ import annotations

import unittest

from agentic_backlog_kit.manifest import ManifestError, validate_manifest

from tests.helpers import item, manifest


class ManifestValidationTests(unittest.TestCase):
    def test_accepts_the_default_five_layer_hierarchy(self) -> None:
        data = manifest(
            item("I-1", item_type="Initiative"),
            item("E-1", item_type="Epic", parent="I-1"),
            item("F-1", item_type="Feature", parent="E-1"),
            item("S-1", item_type="Story", parent="F-1"),
            item("T-1", item_type="Task", parent="S-1"),
            item("B-1", item_type="Bug", parent="F-1"),
        )

        normalized = validate_manifest(data)

        self.assertEqual(6, len(normalized["items"]))

    def test_rejects_duplicate_ids(self) -> None:
        with self.assertRaisesRegex(ManifestError, "Duplicate item id"):
            validate_manifest(manifest(item("T-1"), item("T-1")))

    def test_rejects_missing_dependency(self) -> None:
        with self.assertRaisesRegex(ManifestError, "unknown dependency"):
            validate_manifest(manifest(item("T-1", depends_on=["T-404"])))

    def test_rejects_invalid_parent_level(self) -> None:
        data = manifest(
            item("I-1", item_type="Initiative"),
            item("T-1", item_type="Task", parent="I-1"),
        )
        with self.assertRaisesRegex(ManifestError, "must be a direct child"):
            validate_manifest(data)

    def test_rejects_dependency_cycle_with_the_cycle_path(self) -> None:
        data = manifest(
            item("T-1", depends_on=["T-2"]),
            item("T-2", depends_on=["T-1"]),
        )
        with self.assertRaisesRegex(ManifestError, r"T-1.*T-2.*T-1"):
            validate_manifest(data)

    def test_rejects_out_of_range_scoring_dimension(self) -> None:
        with self.assertRaisesRegex(ManifestError, "impact must be an integer from 1 to 5"):
            validate_manifest(manifest(item("T-1", impact=6)))

    def test_rejects_unknown_item_fields(self) -> None:
        backlog_item = item("T-1")
        backlog_item["agent_guess"] = True

        with self.assertRaisesRegex(ManifestError, "unknown fields.*agent_guess"):
            validate_manifest(manifest(backlog_item))

    def test_rejects_non_string_parent_with_a_manifest_error(self) -> None:
        backlog_item = item("T-1")
        backlog_item["parent"] = ["F-1"]

        with self.assertRaisesRegex(ManifestError, "parent must be an item id or null"):
            validate_manifest(manifest(backlog_item))

    def test_rejects_invalid_iteration_during_general_validation(self) -> None:
        data = manifest(item("T-1"))
        data["workflow"]["iteration"] = {
            "field": "Sprint",
            "start_date": "not-a-date",
            "duration_days": 14,
        }

        with self.assertRaisesRegex(ManifestError, "start_date must use YYYY-MM-DD"):
            validate_manifest(data)


if __name__ == "__main__":
    unittest.main()
