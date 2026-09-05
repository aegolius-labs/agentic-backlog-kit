from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
SHARED_RELEASE = (
    "aegolius-labs/.github/.github/workflows/conventional-release.yml@v0.1.1"
)


class ReleaseWorkflowTests(unittest.TestCase):
    def test_uses_the_versioned_organization_release_workflow(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertEqual(2, workflow.count(f"uses: {SHARED_RELEASE}"))
        self.assertIn("if: ${{ github.ref == 'refs/heads/main' }}", workflow)
        self.assertIn("dry-run: true", workflow)
        self.assertIn("dry-run: false", workflow)
        self.assertNotIn("gh release create", workflow)

    def test_validates_computed_version_before_creating_release(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("needs: compute-version", workflow)
        self.assertIn("needs.compute-version.outputs.new-tag", workflow)
        self.assertIn(
            'python scripts/release_check.py --tag "$RELEASE_TAG" --dist dist',
            workflow,
        )
        self.assertIn("needs: [compute-version, preflight]", workflow)

    def test_attaches_only_the_preflighted_distributions(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("actions/download-artifact@v4", workflow)
        self.assertIn('gh release upload "$RELEASE_TAG" dist/*', workflow)
        self.assertIn("needs.release.outputs.released == 'true'", workflow)


if __name__ == "__main__":
    unittest.main()
