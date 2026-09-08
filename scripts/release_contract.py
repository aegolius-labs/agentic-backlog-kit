"""Validate the actual caller/callee contract; YAML parsing is a CI-only dependency."""
from __future__ import annotations

import argparse
from pathlib import Path
import re


class ContractError(ValueError):
    pass


def validate_shared_reference(pin, comparison):
    """Require a durable accepted revision, not a readable abandoned PR commit."""
    if (comparison.get('status') not in ('identical', 'ahead')
        or comparison.get('base_commit', {}).get('sha') != pin
        or comparison.get('merge_base_commit', {}).get('sha') != pin):
        raise ContractError('Shared workflow pin must belong to shared main history; '
                            're-pin after a squash merge')


def validate_contract(caller, compute, publisher):
    def require(condition, message):
        if not condition:
            raise ContractError(message)

    jobs = caller['jobs']
    calculate, preflight, publish = (jobs[name] for name in ('compute-version', 'preflight', 'release'))
    prefix = 'aegolius-labs/.github/.github/workflows/'
    pins = []
    for job, filename in ((calculate, 'compute-release.yml'), (publish, 'publish-release-assets.yml')):
        match = re.fullmatch(re.escape(prefix + filename) + r'@([0-9a-f]{40})', job['uses'])
        require(match is not None, 'Shared workflows require exact commit pins')
        pins.append(match.group(1))
    require(pins[0] == pins[1] == publish['with']['automation-sha'], 'Automation source pin differs from workflow pin')
    require(calculate['permissions'] == {'contents': 'read'}, 'Computation caller must be read-only')
    for name, callee, caller_job in (('compute', compute, calculate), ('publish', publisher, publish)):
        for job in callee['jobs'].values():
            permissions = job.get('permissions', callee.get('permissions', {}))
            for permission, level in permissions.items():
                available = caller_job.get('permissions', {}).get(permission, 'none')
                require({'none': 0, 'read': 1, 'write': 2}[level] <= {'none': 0, 'read': 1, 'write': 2}[available],
                        f'{name} requests permission beyond its caller: {permission}')
        invocation = callee.get('on', callee.get(True, {}))['workflow_call']
        required = {key for key, value in invocation.get('inputs', {}).items() if value.get('required')}
        require(required <= set(caller_job.get('with', {})), f'{name} missing required inputs')
        require(set(caller_job.get('with', {})) <= set(invocation.get('inputs', {})), f'{name} has undeclared inputs')
        expected_outputs = ({'new-tag', 'new-version', 'candidate-sha', 'tag-state-sha256', 'changelog'}
                            if name == 'compute' else {'released', 'release-id'})
        require(expected_outputs <= set(invocation.get('outputs', {})), f'{name} missing required outputs')
    compute_steps = compute['jobs']['compute']['steps']
    versions = [step for step in compute_steps if step.get('uses', '').startswith('mathieudutour/github-tag-action@')]
    require(len(versions) == 1, 'Expected one shared version calculator')
    require(str(versions[0]['with']['dry_run']).lower() == 'true', 'Version calculator may write')
    require(str(versions[0]['with']['default_bump']).lower() == 'false', 'No-bump policy changed')
    require(str(versions[0]['with']['fetch_all_tags']).lower() == 'true', 'Version calculator truncates tag history')
    require(preflight['needs'] == 'compute-version', 'Preflight must depend on computation')
    require(set(publish['needs']) == {'compute-version', 'preflight'}, 'Publication bypasses preflight')
    require("needs.preflight.result == 'success'" in publish['if'], 'Publication is not success-gated')
    require(publish['with']['candidate-sha'] == '${{ needs.compute-version.outputs.candidate-sha }}', 'Candidate not bound to computation')
    require(publish['with']['tag'] == '${{ needs.compute-version.outputs.new-tag }}', 'Tag not bound to computation')
    require(publish['with']['artifact-id'] == '${{ needs.preflight.outputs.artifact-id }}', 'Artifact not bound to preflight')
    require(publish['with']['inventory-sha256'] == '${{ needs.preflight.outputs.inventory-sha256 }}', 'Inventory not bound to preflight')
    uploads = [step for step in preflight['steps'] if step.get('uses', '').startswith('actions/upload-artifact@')]
    require(len(uploads) == 1 and uploads[0]['with']['path'] == 'release-bundle/', 'Upload must contain exact bundle')
    require(int(uploads[0]['with']['retention-days']) >= 30, 'Bundle expires before recovery window')
    checks = [step for step in preflight['steps'] if step.get('uses', '').startswith('actions/checkout@')]
    require(checks[0]['with']['ref'] == '${{ needs.compute-version.outputs.candidate-sha }}', 'Build checkout is not candidate-bound')
    steps = publisher['jobs']['publish']['steps']
    downloads = [step for step in steps if step.get('uses', '').startswith('actions/download-artifact@')]
    require(len(downloads) == 1, 'Expected one bundle download')
    require(downloads[0]['with']['artifact-ids'] == '${{ inputs.artifact-id }}', 'Publisher searches by name instead of artifact identity')
    require(not ({'run-id', 'repository', 'github-token'} & set(downloads[0]['with'])), 'Publisher may download from another run')
    checkouts = [step for step in steps if step.get('uses', '').startswith('actions/checkout@')]
    require(checkouts[0]['with']['repository'] == 'aegolius-labs/.github', 'Wrong automation repository')
    require(checkouts[0]['with']['ref'] == '${{ inputs.automation-sha }}', 'Automation code not bound')
    require(checkouts[0]['with']['persist-credentials'] is False, 'Checkout persists write credentials')
    return pins[0]


def main():
    import yaml  # CI/audit tooling only; not needed by the packaged runtime or unit tests.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--caller', type=Path, default=Path('.github/workflows/release.yml'))
    parser.add_argument('--shared', type=Path, default=Path('tests/fixtures/organization-release'))
    parser.add_argument('--verify-remote', action='store_true', help='Compare fixtures with the exact public shared commit')
    args = parser.parse_args()
    documents = [yaml.safe_load(path.read_text(encoding='utf-8-sig')) for path in
                 (args.caller, args.shared / 'compute-release.yml', args.shared / 'publish-release-assets.yml')]
    pin = validate_contract(*documents)
    if args.verify_remote:
        import json
        from urllib.request import Request, urlopen
        comparison_url = f'https://api.github.com/repos/aegolius-labs/.github/compare/{pin}...main'
        request = Request(comparison_url, headers={'Accept': 'application/vnd.github+json',
                                                  'User-Agent': 'agentic-backlog-kit-contract'})
        with urlopen(request, timeout=30) as response:
            validate_shared_reference(pin, json.load(response))
        for filename, expected in zip(('compute-release.yml', 'publish-release-assets.yml'), documents[1:]):
            url = f'https://raw.githubusercontent.com/aegolius-labs/.github/{pin}/.github/workflows/{filename}'
            with urlopen(url, timeout=30) as response:
                actual = yaml.safe_load(response.read().decode('utf-8-sig'))
            if actual != expected:
                raise ContractError(f'Fixture differs from pinned shared workflow: {filename}')
    print(f'Release contract valid at {pin}')


if __name__ == '__main__':
    main()
