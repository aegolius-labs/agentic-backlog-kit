# Release-candidate validation evidence

This record covers the final Wave C candidate checks and the Wave D `0.1.0`
publication on 2026-09-04. The tagged release commit is
`6a14b704d22e27cea693d5b764b2d2027919d939`. Approved GitHub mutations and
their safety boundaries are recorded explicitly below and in the R02
capability evidence.

## Results

| Check | Windows/tag clone | Ubuntu WSL | Hosted `ubuntu-latest` |
| --- | ---: | ---: | ---: |
| Complete test suite | 168 passed | 163 passed | 168 passed |
| CLI help | passed | passed | passed |
| R09 benchmark (`100`, `1,000`, `10,000`) | passed | passed | passed |
| Build sdist and wheel | passed | passed | passed |
| Install wheel and run `abk --help` | passed | passed | passed |

The 2026-09-04 Windows benchmark report is 9,421 bytes with SHA-256
`0c8e76542847797eda4d30c764476599cc253e1725fd339d889e83df846addf3`.
A second Windows run and the Linux run produced the same digest; it is also
identical to the 2026-08-27 baseline, and all budget failures were empty. The
compact baselines are recorded in
[benchmarks.md](benchmarks.md).

## Wave D publication evidence

- Public repository: [aegolius-labs/agentic-backlog-kit](https://github.com/aegolius-labs/agentic-backlog-kit),
  repository ID `1357618080`, node `R_kgDOUOuboA`.
- `main` and annotated tag `v0.1.0` resolve to release commit `6a14b70`.
- The exact-commit hosted [test workflow](https://github.com/aegolius-labs/agentic-backlog-kit/actions/runs/33922592690)
  completed successfully with 168 tests, package smoke testing, release
  preflight, and token-budget validation.
- `main` requires the strict `test` status context with administrator
  enforcement; force pushes and branch deletion are disabled. No pull-request
  review count was invented for the initial single-maintainer release.
- The tag-triggered [release workflow](https://github.com/aegolius-labs/agentic-backlog-kit/actions/runs/33922721178)
  completed successfully and published the non-draft, non-prerelease
  [`v0.1.0` release](https://github.com/aegolius-labs/agentic-backlog-kit/releases/tag/v0.1.0).
- A clean public clone at `v0.1.0` reproduced the release commit and passed the
  full suite, CLI, byte budgets, plugin validator, and all five skill
  validators.

The published assets were downloaded and independently passed
`release_check.py`; the wheel was installed without dependencies and reported
runtime version `0.1.0`:

| Published artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `agentic_backlog_kit-0.1.0-py3-none-any.whl` | 60,792 | `b138e453568eb6aff899e270c0c2c0a0f4e7237bba765b59ce56189ea0b67b51` |
| `agentic_backlog_kit-0.1.0.tar.gz` | 91,917 | `79243e76f753cd9ddded307d4b2890453362c44a9a4c4d1d3d57b6f43ef07fea` |

Archive timestamps can make a local build's digest differ from the hosted
build. Release verification therefore checks exact names, metadata, version,
entry point, legal files, and source structure, and records the authoritative
published digests rather than claiming byte-for-byte reproducibility.

## Wave C GitHub capability evidence

The redacted [capability record](../evals/live_github/capability-gap.wave-c-r02.json)
captures the disposable evaluation preflight and apply results:

| Route | Result | Release interpretation |
| --- | --- | --- |
| Authenticated GitHub CLI | Label-fallback workflow converged with eight managed issues, Project memberships, relationships, fields, and a zero-action second plan | Supported native route |
| Direct GraphQL/REST | Same label-fallback convergence and zero-action second plan | Supported peer native route |
| Capability-complete Codex GitHub integration/MCP | Conditional support; capability preflight must prove the complete operation and identity surface | Supported when complete |
| Installed generic GitHub MCP | Failed preflight before writes; Projects, fields/views/iterations, hierarchy/dependencies, repository lifecycle, native issue types, and rate-limit capabilities were unavailable | Not a supported complete route |

The organization used for the evaluation did not expose the canonical native
`Story` issue type (it exposed `User Story` and `Tech Story` instead). Native
type scenarios therefore stopped at preflight; the label-fallback scenarios
used the corresponding `type:<lowercase>` labels. The direct-API synchronization
also recorded temporary residual Project-membership additions on its immediate
recheck; a later read-only refresh converged, and no old plan was replayed.

The supported mutation boundary is additive and update-only: managed issues,
Project membership and fields, parent relationships, and missing dependencies
may be created or updated. Issue deletion, relationship removal, Project-item
archival, and automatic issue closure are outside the release. Project-view
grouping and sorting drift likewise fails closed because GitHub's current view
update input cannot safely change those settings; same-name views are never
deleted and recreated.

The separately approved evaluation cleanup deleted and verified absence of GH
Project #4, then stopped on the first failed repository deletion without a
retry. The GH evaluation repository remains; the API Project #5 and repository
were untouched. Concurrent creation of the canonical public repository also
changed a protected plan precondition, so any remaining cleanup requires a new
identity-bound plan and confirmation. This partial cleanup does not affect the
preserved evaluation results or the release.

## Linux route and limits

The host is Windows. A read-only WSL probe found Ubuntu 20.04.6 LTS running
as WSL 1; Docker Desktop was stopped and its Linux daemon pipe was absent. The
distro's system interpreter is Python 3.8.10, below this package's declared
Python `>=3.11` requirement. For this validation only, the published
CPython 3.11.16 `x86_64-unknown-linux-gnu` install-only archive from the
[20260825 python-build-standalone release](https://github.com/astral-sh/python-build-standalone/releases/tag/20260825)
was downloaded to `/tmp` and verified before use:

```text
sha256:25844eb97cdc72cdc78addaad0969ce3b2133a4de54bfcfa4d57f8a6d095eaab
```

The mounted checkout was tested with commands equivalent to the Linux CI
workflow:

```sh
PYTHONPATH=src /tmp/abk-rc-python311/python/bin/python3.11 -m unittest discover -s tests -v
/tmp/abk-rc-python311/python/bin/python3.11 scripts/backlog.py --help
/tmp/abk-rc-python311/python/bin/python3.11 scripts/benchmark.py --check
/tmp/abk-rc-python311/python/bin/python3.11 -m build
/tmp/abk-rc-python311/python/bin/python3.11 -m pip install --force-reinstall dist/*.whl
/tmp/abk-rc-python311/python/bin/abk --help
```

This remains useful local Linux/WSL evidence. Wave D additionally ran the same
repository workflow on hosted `ubuntu-latest`; the successful run and branch
protection result are recorded above.


## R14 corrective implementation local evidence

The corrected ABK caller pins the new shared compute/publisher workflows and
publisher source to local commit `194c01743a7a41d75c41e1434d8ca02b3702a586` in
`aegolius-labs/.github`. This commit has not yet been published. ABK's original
R14 publication Plan F is superseded; replacement Plan G proposes exact branch
pushes and draft PRs only.

Checks performed on the local corrective working tree:

- Final full ABK suite: 182 passed in 79.964 seconds; focused final
  contract/inventory suite: 14 passed.
- Shared suite: 18 passed, including actual compute-script execution with fake
  read responses, drift, draft/partial-upload recovery, foreign assets, and a
  lost publication response.
- ABK package inventory -> shared publisher fake-transport integration: passed.
- CLI help, 100/1,000/10,000-item byte budgets, build, release metadata/asset
  preflight, and a clean temporary wheel install with abk --help: passed.
- Bundled plugin validator: passed. No skills changed.
- Actual caller/callee YAML contract check using existing local PyYAML: passed.
  CI additionally fetches the pinned public shared workflow files and compares
  them with the fixtures. That remote check awaits shared commit publication.
- actionlint 1.7.12 passed on both new shared workflows, their test workflow,
  and both ABK workflows. Optional ShellCheck/Pyflakes integrations were not run.
  The official Windows archive SHA-256 was verified as
  `6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9`.

The local build produced a wheel of 60,995 bytes, SHA-256
`4a0458a98f408148f5dcce1a8642cf0a81109e8a9d929bb0b3bca15b0b14af9e`, and sdist of
95,168 bytes, SHA-256
`c012efa45b1168d7a2873d663ab6c154b9efc7063947dffe6712da8ca277d3a4`.
These are smoke-test artifacts, not replacements for immutable v0.1.0 assets.

Read-only GitHub checks confirmed owner-enforced immutable releases in both
repositories. ABK main remains `6a14b70` with strict test protection. Organization
main remains `c7380d9`, with a PR/code-owner approval requirement, squash-only
merge, conversation resolution, and CodeQL rules. Both proposed branches are
absent and have no open PR duplicates. No external writes occurred.

Hosted parser/CI proof, no-bump execution on main, and a separately authorized
immutable-release evaluation remain outstanding. Local fake transports and
syntax validation do not satisfy those gates. Record their exact commits and
run/release URLs before closing R14.

R14 benchmark report SHA-256: `0c8e76542847797eda4d30c764476599cc253e1725fd339d889e83df846addf3`; all budgets passed.
