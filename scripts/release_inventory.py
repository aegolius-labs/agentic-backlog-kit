"""Create the verified distribution bundle consumed by organization automation."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

try:
    from scripts.release_check import validate_release, ReleaseCheckError
except ModuleNotFoundError:
    from release_check import validate_release, ReleaseCheckError


def create_inventory(root, dist, bundle, *, repository, sha, tag, tag_state, notes=''):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ReleaseCheckError('Invalid repository identity')
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ReleaseCheckError('Candidate must be a full commit SHA')
    if not re.fullmatch(r'[0-9a-f]{64}', tag_state):
        raise ReleaseCheckError('Missing version-computation tag fingerprint')
    report = validate_release(root, dist, tag=tag)
    # A dedicated empty directory prevents stale or unvalidated assets entering the bundle.
    if bundle.exists() and any(bundle.iterdir()):
        raise ReleaseCheckError('Release bundle must be empty')
    bundle.mkdir(parents=True, exist_ok=True)
    data = {'schema_version': 1, 'repository': repository, 'candidate_sha': sha,
            'tag': tag, 'version': report.version, 'tag_state_sha256': tag_state,
            'notes': notes, 'assets': [asdict(asset) for asset in report.artifacts]}
    for asset in report.artifacts:
        source = dist / asset.name
        if source.is_symlink():
            raise ReleaseCheckError('Distribution must be a regular file')
        target = bundle / asset.name
        shutil.copyfile(source, target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != asset.sha256:
            raise ReleaseCheckError('Distribution changed while copying')
    raw = json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8') + b'\n'
    (bundle / 'release-inventory.json').write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    parser.add_argument('--bundle', type=Path, default=Path('release-bundle'))
    args = parser.parse_args()
    try:
        result = create_inventory(args.root, args.dist, args.bundle,
                                  repository=os.environ['GITHUB_REPOSITORY'],
                                  sha=os.environ['CANDIDATE_SHA'], tag=os.environ['RELEASE_TAG'],
                                  tag_state=os.environ['TAG_STATE_SHA256'],
                                  notes=os.environ.get('RELEASE_NOTES', ''))
    except (OSError, KeyError, ReleaseCheckError) as exc:
        parser.exit(1, f'Release bundle failed: {exc}\n')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write(f'inventory-sha256={result}\n')
    print(f'Validated release inventory: {result}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
