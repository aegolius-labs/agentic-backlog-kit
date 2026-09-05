from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.release_inventory import create_inventory
from scripts.release_check import ReleaseCheckError
from tests.test_release_check import ROOT, _write_artifacts


class ReleaseInventoryTests(unittest.TestCase):
    def build(self, dist, bundle, **overrides):
        options = dict(repository='aegolius-labs/agentic-backlog-kit', sha='a' * 40,
                       tag='v0.1.0', tag_state='b' * 64, notes='Reviewed release notes')
        options.update(overrides)
        return create_inventory(ROOT, dist, bundle, **options)

    def test_binds_exact_distribution_bytes_candidate_and_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dist = root / 'dist'
            dist.mkdir()
            _write_artifacts(dist)
            bundle = root / 'bundle'
            result = self.build(dist, bundle)
            raw = (bundle / 'release-inventory.json').read_bytes()
            data = json.loads(raw)
            self.assertEqual(result, hashlib.sha256(raw).hexdigest())
            self.assertEqual('a' * 40, data['candidate_sha'])
            self.assertEqual('v0.1.0', data['tag'])
            self.assertEqual('b' * 64, data['tag_state_sha256'])
            self.assertEqual(2, len(data['assets']))
            self.assertEqual(3, len(list(bundle.iterdir())))
            for asset in data['assets']:
                payload = (bundle / asset['name']).read_bytes()
                self.assertEqual(asset['size'], len(payload))
                self.assertEqual(asset['sha256'], hashlib.sha256(payload).hexdigest())

    def test_metadata_mismatch_prevents_bundle_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_artifacts(root)
            with self.assertRaisesRegex(ReleaseCheckError, 'does not match'):
                self.build(root, root / 'bundle', tag='v0.1.1')
            self.assertFalse((root / 'bundle').exists())

    def test_rejects_stale_bundle_and_extra_distribution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_artifacts(root)
            bundle = root / 'bundle'
            bundle.mkdir()
            (bundle / 'stale.whl').write_bytes(b'stale')
            with self.assertRaisesRegex(ReleaseCheckError, 'empty'):
                self.build(root, bundle)
            (root / 'extra.whl').write_bytes(b'extra')
            with self.assertRaises(ReleaseCheckError):
                self.build(root, root / 'other-bundle')
            self.assertFalse((root / 'other-bundle').exists())

    def test_rejects_unbound_identity_and_tag_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for overrides in ({'sha': 'main'}, {'tag_state': ''}, {'repository': '../elsewhere'}):
                with self.subTest(overrides=overrides), self.assertRaises(ReleaseCheckError):
                    self.build(root, root / 'bundle', **overrides)


if __name__ == '__main__':
    unittest.main()
