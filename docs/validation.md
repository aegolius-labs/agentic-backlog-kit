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

Historical pre-publication checkpoint. The activation record below supersedes
its delivery status; these local test results remain historical evidence.

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


## R14 merge and activation evidence

On 2026-09-08, user-authorized activation merged [shared PR #4](https://github.com/aegolius-labs/.github/pull/4)
at `9f323e5ef1266f90f6b10c3aa3a595a0f3542ab9` and [ABK PR #1](https://github.com/aegolius-labs/agentic-backlog-kit/pull/1)
at `33142d846e4faec7e1d0ed184ac745f4f987c8f5`. The user separately authorized the
existing organization-admin review bypass for shared PR #4. Protection and
immutability settings were unchanged. Both squash merge trees matched their
reviewed candidates; the shared repository automatically deleted its PR branch.

Shared main test/release checks passed with no new tag or release. ABK's
[main test run](https://github.com/aegolius-labs/agentic-backlog-kit/actions/runs/34179794480)
passed. Its [release run](https://github.com/aegolius-labs/agentic-backlog-kit/actions/runs/34179794722)
failed loading `compute-release.yml@194c017...`, before any jobs started. The old
commit remained raw-readable but diverged from shared main history; GitHub
reported the workflow was not found. Receipt H stopped after both merges.
v0.1.0 and its assets remained unchanged; no failed operation was replayed.

The correction pins the accepted shared merge commit and verifies main ancestry
before comparing file contents. Three added regression cases cover accepted,
diverged, unmerged, incomplete, and mismatched ancestry responses. The tests first
failed because the validator did not exist, then all 13 workflow-contract tests
passed. The corrected live remote contract check passed. The full suite passed
185 tests in 83.337 seconds; CLI help, actionlint 1.7.12, and patch whitespace
checks passed. The bundled plugin validator passed using the existing local
validator dependencies. No skill changed. Hosted activation evidence remains required.

## R14 hosted activation and immutable publication (2026-09-13)

On 2026-09-13, approved Plan L completed all five actions. The unchanged fixture
main `1bba7e6790c410631d562227379b269c5dade6f7`, with an explicitly approved
`v0.0.0` baseline at `55a6dc3e9616a0e8cd446cf84c78d7fa48328428`, passed
[hosted compute, preflight and publication](https://github.com/aegolius-labs/abk-release-eval-20260908/actions/runs/34781149178). Its
[immutable v0.1.0 release](https://github.com/aegolius-labs/abk-release-eval-20260908/releases/tag/v0.1.0) contains exactly the preflighted wheel and
source archive. Downloaded names, sizes and SHA-256 hashes matched; package
metadata, isolated wheel installation and `abk --help` passed. The publisher
receipt records draft asset verification before publication and final verification.
Production main commits, protections, immutability settings and release inventories
were unchanged. The fixture is retained; no cleanup occurred.

R14 remains ongoing: untagged release-bearing history silently analyzed zero
commits before baseline setup (R14-F7). Document and enforce the baseline
prerequisite without automatic tag creation, and separately prove hosted recovery
after draft creation and partial upload. Local recovery tests alone do not close
that gate. R15 is the next product implementation item; D1 and carryover policy A
are approved. This documentation refresh is local and has not been published.

Production no-bump run 34180532203 passed after PR #2. Prior local validation
recorded 185 tests; this documentation-only turn did not rerun that suite.
Plan L hosted preflight ran the unchanged suite and package checks successfully.
The same fixture main test run 34260384360 was freshly confirmed successful.

Publisher release ID: `388026880`. Inventory SHA-256:
`2167b2f73f5b699a4b41ff795478448ca6fdbf055a35fe08bb639a64a543c833`.

| Published file | Bytes | SHA-256 |
| --- | ---: | --- |
| agentic_backlog_kit-0.1.0-py3-none-any.whl | 60948 | 3571e66925e886090b8f71ce116b5a18de936998ad1ed609665de1236e489c13 |
| agentic_backlog_kit-0.1.0.tar.gz | 94333 | 6e9990d9136cbd7d31de39b86fe66bda199215cd439770a4dffc67f5ac2860cb |

The receipt's completed order is tag creation, draft creation, two asset
uploads, draft asset verification, publication request, published verification.
These are evaluation assets, not replacements for the production v0.1.0 assets.
The first local read-only preflight attempt lacked sandbox network access; it
made no external write. Its recorded infrastructure failure was followed by an
authorized network-enabled read-only refresh. The baseline tag and dispatch each
occurred exactly once. No workflow failure or recovery was injected in Plan L.

## R14 hosted recovery after draft creation and partial upload (2026-09-24)

Approved Plan M (digest
`e8964ea97ece2bd9c14f5200e2c5612649725bdef6f6775e0b5c8f510e6e3e0f`) closed
S-R14-2 against the same retained fixture. Production repositories, protections,
immutability settings and the shared pin `9f323e5` were not touched.

1. Fixture commit `213442a3a2187f07590ae35e3cfaf118d0319c18`
   (`fix: record R14 recovery proof fixture`) passed
   [test](https://github.com/aegolius-labs/abk-release-eval-20260908/actions/runs/35951466135)
   on a branch and was fast-forwarded onto fixture `main`. The fixture predates
   computed version stamping, so the commit stamps `0.1.1` into its version
   files, changelog and version-bound tests by hand; the approved plan named only
   a documentation file, and this was the one deviation.
2. [Release run 35951524172](https://github.com/aegolius-labs/abk-release-eval-20260908/actions/runs/35951524172)
   computed `v0.1.1`, and preflight passed and uploaded bundle artifact
   `10788962030` with inventory SHA-256
   `fa6c3d73e44d95b009e42601edd7eecb447b936640413b201054dd45a09076c9`.
   The run was cancelled while the publish job was still in `Set up job`, so
   attempt 1 made no GitHub write: no tag, no draft, no asset.
3. The partial state was then produced by hand, from that exact downloaded
   bundle, using the pinned publisher's own `GitHub` transport methods after the
   same head, tag-state and no-existing-release checks: tag `v0.1.1` at the
   candidate, draft release `395291910` whose body is the inventory notes plus
   the inventory marker, and the wheel only. The uploaded wheel read back as
   `uploaded`, 60952 bytes, with the inventory hash.
4. Re-running the failed jobs produced attempt 2. Compute and preflight were
   carried over, not re-executed, and the publisher downloaded the same artifact
   `10788962030` with the same inventory hash. It accepted the matching draft,
   verified the existing wheel before any write, uploaded only the sdist,
   verified the draft, published and verified. The attempt-2 receipt's completed
   steps are exactly `asset_uploaded:agentic_backlog_kit-0.1.1.tar.gz`,
   `draft_assets_verified`, `publication_requested`,
   `published_assets_verified` - no `tag_created`, no `draft_created`, no
   replacement.

Independent readback afterwards: release `395291910` is published, not a
prerelease, `immutable: true`, marked latest, targets the candidate, and has
exactly the two inventory assets. Tag `v0.1.1` points at the candidate; `v0.1.0`
(release `388026880`, `1bba7e6`) and `v0.0.0` are unchanged. Downloaded assets
matched the inventory, and an isolated no-dependency wheel install ran
`abk --help`. Immutability remains enabled and owner-enforced.

| Published file | Bytes | SHA-256 |
| --- | ---: | --- |
| agentic_backlog_kit-0.1.1-py3-none-any.whl | 60952 | 405cd50490e8484b44c1c8e232d8173973b647dfbfdc25e6d955146edc0b499d |
| agentic_backlog_kit-0.1.1.tar.gz | 94322 | 7f20d1b97ae8a1569d1a49bf7c2412620284a8792946c483af5b0d464f9fe7e2 |

What this proves and what it does not: the organization publisher, on hosted
infrastructure, resumes a failed publication from a matching draft that holds a
subset of verified assets, using the original bundle and inputs, without
recreating or replacing anything. The partial state was written by the operator
rather than left by a publisher that failed mid-upload, because the publisher has
no fault-injection hook and a mid-upload cancellation cannot be timed reliably.
The writes were the publisher's own calls in the publisher's own order, so the
state is the one a mid-upload failure leaves. A half-uploaded asset (state other
than `uploaded`) is not auto-recovered by design: the publisher stops for
reviewed remediation, which the shared suite covers locally. These are
evaluation assets, not product releases. The fixture is retained for R20.

## R20 fresh resource discovery (2026-09-24)

S-R20-1 re-enumerated `aegolius-labs` repositories (all visibilities) and every
organization Project including closed ones, read-only, and matched them against
the Wave C cleanup receipt in
[the capability record](../evals/live_github/capability-gap.wave-c-r02.json).
Nothing was deleted or changed.

Project #4 is absent: the organization Project list does not contain it and
`projectV2(number: 4)` resolves `NOT_FOUND`. The four `-native` and `-mcp-`
scenario repositories named in the record return 404; those scenarios stopped
at preflight before any write, so they were never created.

Remaining disposable evaluation resources:

| Resource | Node ID | Visibility | Created | Contents | Receipt match |
| --- | --- | --- | --- | --- | --- |
| repository `abk-eval-wave-c-r02-20260827-gh-26c954aa-labels` | `R_kgDOUKTD5Q` | private | 2026-09-01 | 8 issues; no releases, tags or hooks | yes - failed deletion target |
| Project #5 `ABK Eval wave-c-r02-20260827-api-3f546dc6 [labels]` | `PVT_kwDOD0x0U84BiD-Q` | private, open | 2026-09-01 | 8 items, linked only to the API repository below | yes |
| repository `abk-eval-wave-c-r02-20260827-api-3f546dc6-labels` | `R_kgDOUKTEpg` | private | 2026-09-01 | 8 issues; no releases, tags or hooks | yes |
| repository `abk-adopt-eval-20260922` | `R_kgDOUmapPg` | private | 2026-09-22 | 10 issues; no releases, tags or hooks | added after the receipt (GH-63) |
| repository `abk-release-eval-20260908` | `R_kgDOUSpIDA` | public | 2026-09-08 | release fixture: tags `v0.0.0`, `v0.1.0`, `v0.1.1`; immutable releases `388026880`, `395291910` | added after the receipt (R14) |

No other forks, hooks or matching repositories or Projects exist, and the
authenticated user owns no repository or Project with an `abk` or `eval` name.

Not evaluation resources, and out of R20 scope: Projects #2 and #3 ("Agentic
Backlog", created 2026-06-16, linked only to `aio-agentic-sdlc`), and the empty
Project #1 (created 2026-05-23, no linked repository). All three predate every
kit evaluation. Project #6 is this repository's own backlog.

The authenticated token's scopes are `admin:org`, `gist`, `project`,
`read:packages`, `repo` and `workflow`. Deleting Project #5 is within `project`;
deleting any repository needs `delete_repo`, which this token lacks - the same
gap behind the original `repository_delete_request_failed` stop and the GH-63
retention.

R20 is now a decision rather than discovery. Each resource above needs either an
explicit retention election or a new identity-bound deletion plan confirmed by
digest, executed with a token that carries `delete_repo`, stopping on the first
failure. The release fixture in particular may be worth retaining: it is the only
place the hosted release path can be exercised without producing product releases.
