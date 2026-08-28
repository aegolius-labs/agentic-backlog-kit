from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentic_backlog_kit.cli import main


class CliTests(unittest.TestCase):
    def test_init_validate_and_prioritize_are_local_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "init",
                            "--manifest",
                            str(manifest_path),
                            "--owner",
                            "aegolius-labs",
                            "--repository",
                            "example",
                            "--project-number",
                            "1",
                        ]
                    ),
                )
            self.assertTrue(manifest_path.exists())

            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    0, main(["validate", "--manifest", str(manifest_path)])
                )

            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["items"] = [
                {
                    "id": "T-1",
                    "title": "First task",
                    "type": "Task",
                    "description": "Do the first useful thing",
                    "acceptance_criteria": ["A test proves it works"],
                    "parent": None,
                    "depends_on": [],
                    "impact": 3,
                    "effort": 2,
                    "business_value": 4,
                    "enabler_value": 0,
                    "status": "Ready",
                    "maturity": "ready",
                    "sprint": None,
                }
            ]
            manifest_path.write_text(json.dumps(data), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    0,
                    main(
                        [
                            "prioritize",
                            "--manifest",
                            str(manifest_path),
                            "--limit",
                            "1",
                        ]
                    ),
                )
            result = json.loads(output.getvalue())
            self.assertEqual("T-1", result["items"][0]["id"])

    def test_init_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            manifest_path.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "already exists"):
                main(
                    [
                        "init",
                        "--manifest",
                        str(manifest_path),
                        "--owner",
                        "aegolius-labs",
                        "--repository",
                        "example",
                        "--project-number",
                        "1",
                    ]
                )
            self.assertEqual("keep", manifest_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
