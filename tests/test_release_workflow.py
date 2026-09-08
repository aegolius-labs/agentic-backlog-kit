from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.release_contract import ContractError, validate_contract

ROOT = Path(__file__).resolve().parents[1]


class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.example = json.loads((ROOT / 'tests/fixtures/organization-release/contract-example.json').read_text())

    def validate(self):
        return validate_contract(*(self.example[name] for name in ('caller', 'compute', 'publisher')))

    def test_accepts_permission_compatible_preflighted_release_contract(self):
        self.assertEqual(40, len(self.validate()))

    def test_rejects_original_callee_write_escalation(self):
        self.example['compute']['jobs']['compute']['permissions']['contents'] = 'write'
        with self.assertRaisesRegex(ContractError, 'beyond its caller'):
            self.validate()

    def test_rejects_write_enabled_version_calculator(self):
        steps = self.example['compute']['jobs']['compute']['steps']
        next(s for s in steps if s.get('id') == 'version')['with']['dry_run'] = 'false'
        with self.assertRaisesRegex(ContractError, 'may write'):
            self.validate()

    def test_rejects_bypassing_preflight(self):
        self.example['caller']['jobs']['release']['needs'] = ['compute-version']
        with self.assertRaisesRegex(ContractError, 'bypasses preflight'):
            self.validate()

    def test_rejects_missing_shared_output(self):
        del self.example['compute']['on']['workflow_call']['outputs']['candidate-sha']
        with self.assertRaisesRegex(ContractError, 'missing required outputs'):
            self.validate()

    def test_rejects_missing_required_publisher_input(self):
        del self.example['caller']['jobs']['release']['with']['artifact-id']
        with self.assertRaisesRegex(ContractError, 'missing required'):
            self.validate()

    def test_rejects_mutable_or_mismatched_shared_pins(self):
        for pin in ('main', 'b' * 40):
            with self.subTest(pin=pin):
                original = deepcopy(self.example)
                self.example['caller']['jobs']['release']['with']['automation-sha'] = pin
                with self.assertRaisesRegex(ContractError, 'pin differs'):
                    self.validate()
                self.example = original

    def test_rejects_download_from_a_different_run(self):
        step = next(s for s in self.example['publisher']['jobs']['publish']['steps']
                    if s.get('uses', '').startswith('actions/download-artifact@'))
        step['with']['run-id'] = '123'
        with self.assertRaisesRegex(ContractError, 'another run'):
            self.validate()

    def test_rejects_unbound_build_and_artifact_inputs(self):
        cases = [('candidate-sha', 'main'), ('artifact-id', '123'), ('inventory-sha256', 'f' * 64)]
        for name, value in cases:
            with self.subTest(name=name):
                original = deepcopy(self.example)
                self.example['caller']['jobs']['release']['with'][name] = value
                with self.assertRaisesRegex(ContractError, 'not bound'):
                    self.validate()
                self.example = original

    def test_rejects_insufficient_recovery_retention(self):
        step = next(s for s in self.example['caller']['jobs']['preflight']['steps']
                    if s.get('uses', '').startswith('actions/upload-artifact@'))
        step['with']['retention-days'] = 1
        with self.assertRaisesRegex(ContractError, 'recovery window'):
            self.validate()


if __name__ == '__main__':
    unittest.main()
