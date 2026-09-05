# Wave E remediation proposal

Status: R14 implemented and locally validated; other corrective items remain proposed. No external publication performed.
Baseline: `185f31161e0ff87bb30e60b215abded339bf76c3`.
Roadmap IDs below are delivery identifiers, not newly created GitHub issues.

Continuation context: [active task handoff](task-handoff.md). Both D1 and D2
are approved; policy A governs carryover.

## Coverage and sequence

| Finding | Item | Priority | Gate |
| --- | --- | --- | --- |
| F1: reusable-workflow permission mismatch | R14 | High | Shared contract and hosted validation |
| F2: assets uploaded after immutable publication | R14 | High | Draft/asset/publication integration proof |
| F3: stale manifest overwrites operational status | R15 | High | Authority policy D1 approved |
| F4: existing sprint work selected again | R16 | Medium | R15; carryover policy D2 approved |
| F5: deep dependency chains raise RecursionError | R17 | Medium | Graph regression tests |
| F6: completed prerequisites receive nonzero scores | R18 | Low | Scoring contract tests |
| Public roadmap differs from local release record | R19 | Medium | Reviewed protected-branch publication |
| Partial disposable-resource cleanup | R20 | Low | Fresh discovery and destructive confirmation |

Repair R14 before publishing its caller. Complete R15/R16 before R10 destructive
reconciliation, R11 adoption, or R12 portfolio expansion. R17/R18 are independent
of those policy changes but share priority code and need coordinated integration.
R19 can proceed as a documentation-only change. R20 does not block a release.
R13 remains an evidence-based transport decision, not a prerequisite to these fixes.

## Reference release workflow

Reviewed remotely at aio-agentic-sdlc main commit
`1a24da707d6866b7b1bc9d11d2cf87c924bc1dfa`:

- [release.yml](https://github.com/aegolius-labs/aio-agentic-sdlc/blob/1a24da707d6866b7b1bc9d11d2cf87c924bc1dfa/.github/workflows/release.yml)
  delegates release creation to the organization workflow with `contents: write`
  on main pushes. It follows the shared main branch; ABK should retain a tested
  versioned reference.
- [publish.yml](https://github.com/aegolius-labs/aio-agentic-sdlc/blob/1a24da707d6866b7b1bc9d11d2cf87c924bc1dfa/.github/workflows/publish.yml)
  builds and publishes to PyPI on `release: published`. It does not attach wheel
  or sdist assets to the GitHub Release. This establishes design intent, not
  proof that a GITHUB_TOKEN-created event starts that second workflow.
- ABK's [pinned organization workflow](https://github.com/aegolius-labs/.github/blob/v0.1.1/.github/workflows/conventional-release.yml)
  declares write permission even in dry-run mode, has an unguarded initial-tag
  bootstrap, and creates a published release immediately.

Preserve organization ownership of version calculation, tags, and release
creation. ABK has no PyPI requirement. Keep asset handling in the same invocation
because GITHUB_TOKEN-created events generally do not start another workflow.
Sources: [permission rules](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations),
[event behavior](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow),
and [immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases).

## R14: repair shared release integration (F1/F2)

### Implementation and remaining gates

Shared local commit `194c01743a7a41d75c41e1434d8ca02b3702a586` implements
`compute-release.yml`, `publish-release-assets.yml`, the publisher, and 18 tests.
ABK pins this exact commit and binds its validated wheel/sdist with a hashed
inventory and one Actions artifact ID. Its 182-test suite and local workflow
contract checks pass. v0.1.1 and existing no-asset callers are unchanged.
The implementation follows the contract below. Hosted no-bump, real immutable
publication, repository reviews, and publication remain outstanding. See
[the current runbook](release.md#ongoing-organization-managed-releases).

1. Add a compute-only reusable entry point with `contents: read` and no tag,
   bootstrap, or release writes. Untagged repositories use a computational
   baseline without pushing a synthetic tag. Keep version logic centralized.
   Granting the existing dry-run call write permission would remove the mismatch
   but would not establish the required read-only preflight contract.
2. Return candidate SHA, previous tag, proposed tag/version, and bump eligibility.
   ABK checks out that exact SHA, requires its test/build/benchmark checks, and
   validates package/runtime/plugin/changelog versions and distributions with
   `release_check.py`. No-bump skips publication. Metadata mismatch reports the
   computed version and files requiring alignment; it performs no release write.
3. Preserve the exact two distribution names, sizes, SHA-256 hashes, candidate
   SHA, and tag in an inventory. Pass the Actions artifact identity and inventory
   to the shared publisher. Suggested inputs are expected SHA/tag and artifact
   identity; final names belong to the shared interface implementation.
4. Give the publisher write permission and required artifact read access. Before
   its first write, verify candidate SHA, previous tag, and computed version
   still match preflight. Do not compare identities only after release creation.
5. Organization-owned code creates the exact tag and a draft release, uploads
   both preflighted assets, verifies the complete inventory and downloaded
   hashes, then publishes. Verify published state and inventory afterward.
   Publication is last so immutability locks the correct assets.
6. Preserve current immediate-release behavior for callers without attached
   assets unless separately migrated. ABK uses the asset-aware path. No new
   package runtime dependency is needed.
7. Distinguish draft-created from released; released means final publication.
   Journal release ID, candidate, inventory, and completed steps. Resume only a
   matching draft, verifying/skipping identical uploaded assets. Mismatches stop
   for reviewed remediation; never clobber assets, delete releases, or rewrite
   tags. An already published matching release is a verified no-op. Choose and
   document artifact retention sufficient for recovery instead of assuming the
   current one-day retention always suffices.

### Acceptance and evidence

- Hosted no-bump run loads successfully and writes nothing; compute-only on an
  untagged fixture creates no bootstrap tag.
- Contract tests inspect effective permissions, job dependencies, and actual
  inputs/outputs against a fixture of the pinned shared version. String-presence
  tests alone cannot establish the contract.
- Failed tests, metadata mismatch, identity/tag drift, missing/extra assets, and
  hash mismatch stop before publication, and before tagging when detectable.
- A separately authorized disposable hosted release with immutability enabled
  creates one tag at the expected SHA and one published release containing
  exactly the validated wheel/sdist. It needs no secondary event-triggered run.
- Failure injection after draft creation and after the first upload proves safe
  recovery or an actionable stop; unrelated/published state is never replaced.
- Record shared version, caller SHA, run URLs, release ID, inventory and results
  before marking complete.

Affected artifacts: organization workflow/tests; ABK release workflow,
`tests/test_release_workflow.py`, release validator/tests if inventory output is
added, runbook, checklist, validation record, and R14 status.

## Product decision form

| Field | Selection | State |
| --- | --- | --- |
| D1: existing-item Status/Sprint authority | Fresh GitHub governs; changes require explicit reviewed transitions; new items use manifest defaults | Approved by user in this task |
| D2: unfinished work assigned elsewhere | A: exclude from automatic selection and offer explicit carryover | Approved by user in this task |

R16 follows approved option A and preserves existing workflow status. These
policy decisions define the implementation contract; they do not authorize
automatic moves or external writes outside the reviewed workflow.

## R15: operational authority (F3)

Compose effective planning state from validated manifest intent and a fresh
canonical issue snapshot containing Status, Sprint, issue state, and identities.
Keep observed operational data disposable rather than silently rewriting the
tracked manifest. New unsynchronized items still use manifest defaults.

Ordinary sync must not derive existing-item Status/Sprint writes from legacy
manifest values. Explicit transition intent includes observed value, desired
value, identity, and fingerprint in the confirmed plan. Refresh before apply;
mark intent fulfilled only after remote verification. Lost receipts must not
replay transitions against newly changed remote state.

Old manifest Status/Sprint values remain readable as initial/legacy values, not
standing write authorization. Document migration and version the plan/schema
contract as necessary; old saved plans require replanning. Content/type/scoring
intent retains existing authority; relationship removal remains R10 scope.

Operational next/sprint commands refresh issues as well as iteration state.
An explicit offline preview is labeled unverified and cannot authorize commitment.
Missing/unmapped/ambiguous operational state blocks commitment. Closed issues
with non-done Project status are conflicts excluded from executable work, without
automatically reopening or closing anything.

Acceptance:

- GitHub Done + manifest Ready stays Done, is excluded by next, and generates no
  ordinary-sync status reversal. Remote-completed prerequisites unblock work.
- Remote Sprint changes survive; missing values never silently use stale intent.
- Explicit transitions require review; subsequent drift aborts before writes;
  converged replans are empty, including interrupted/retried operations.
- New items initialize normally; offline previews disclose limits; old plans and
  duplicate identities fail safely.
- Exercise CLI, snapshots, planning, and sync together through fake CLI/API
  transports while retaining canonical transport equivalence.

Affected artifacts: manifest migration, snapshot/CLI/sync/planning inputs, tests,
architecture and README, plus prioritize/sprint/ingest/sync skills and references.

## R16: preserve commitments and review carryover (F4)

Approved D2 design: automatically select eligible unassigned work. Report
items already assigned to the target as retained commitments, not new selections;
count unfinished retained effort once against total target capacity. Preserve
In Progress/In Review and other existing operational statuses. Done work uses
no new capacity. If retained work exceeds capacity, report overage and add none.

Exclude items in another active or completed sprint with a compact explanation.
Offer an explicit carryover preview with source/target identities, IDs, effort,
and preserved status. Use current effort conservatively unless the user supplies
an explicit remaining-work estimate. Moving work requires a reviewed transition.
Only newly assigned Ready work may transition to Planned as part of that plan;
never apply Planned indiscriminately to ongoing/retained work.

A prerequisite assigned elsewhere is satisfied only if done, retained in the
target, or included in the same confirmed dependency-safe commitment. Merely
proposing its carryover is insufficient. Existing R05 identity checks still apply.

Acceptance: current/other/completed sprint cases, preserved statuses, retained
capacity/overage, repeat plans without duplicate effort, explicit carryover and
stale-state rejection and cross-sprint dependencies under approved option A. No automatic move, hidden overrun, or status regression.

Affected artifacts: sprint/CLI/transition integration, sprint and integration
tests, sprint skill/contract, and architecture.

## R17: remove dependency-depth sensitivity (F5)

Use explicit-stack cycle detection with stable cycle diagnostics and reverse
topological scoring with deterministic dependent iteration. Preserve rounding,
ordering and mathematical results. Do not raise recursion limits or truncate boosts.

Acceptance: 1,200- and 10,000-node valid chains pass validate/prioritize/next/sprint
and sync planning; input permutations and opposite dependency direction yield
stable appropriate results. Deep cycles return ManifestError, not RecursionError.
Include diamonds, fan-out, disconnected graphs, stable ties and bounded error
output. Use tiny mathematical oracles plus large structural cases. Label byte
budgets as shallow-fixture output checks; graph correctness is separate and has
no brittle timing threshold.

Affected artifacts: manifest/priority code, graph/CLI tests, benchmark scope
documentation/fixtures, and validation evidence.

## R18: zero completed final scores (F6)

Zero both base and final scores for every configured done status. Add no boosts
to completed nodes and do not propagate boosts through them. Preserve topology
and independent executable filtering. Operational mode uses R15 effective status.

Acceptance: Done A -> Ready B scores 0 and 15 with the existing default fixture;
cover custom done statuses, multiple dependents, all-done graphs, and an unfinished
ancestor behind a completed intermediary. Unfinished graphs keep their existing
scores/ties. Extend the existing isolated-completion test with these graph cases.

Affected artifacts: priority code/tests, R15/R17 integration, and scoring docs.
The documented zero-score rule remains the intended contract.

## R19: publish accurate delivery status

Prepare a documentation-only protected-branch change for verified Wave D closure
and explicit R14 remediation gates. Separate it from unresolved automation code.
Do not rewrite the immutable v0.1.0 tag; historical tagged documents stay historical.

Acceptance after separately authorized publication: public main roadmap,
checklist, and validation agree that v0.1.0 shipped and R14 needs hosted proof.
Read the resulting public SHA/files and record URLs. Local edits are not publication.

## R20: close disposable cleanup independently

Read the prior receipt and refresh exact identities of the remaining GH-lane
private repository and API-lane Project #5/repository; confirm Project #4 absence.
Names and old numbering alone are not deletion authority. Prepare remaining
exact-target actions, preconditions, order and failure handling; obtain a new
digest confirmation before destructive execution. Stop/journal first failure,
then read back resource absence. Report missing permissions without bypassing.
Complete only on verified absence or explicit owner retention decision. Cleanup
is not authorized by this proposal request and does not block product delivery.

## Completion rules

Prior analysis passed 171 tests, CLI help, byte budgets, and plugin/five-skill
validators. In-memory examples reproduced F3-F6; F1/F2 were static findings, not
live experiments. Those passing checks do not validate these proposed fixes.

Implementation must run mandatory suite/help checks, item-specific regressions,
plugin validation, and validators for every changed skill. Record exact SHA,
commands/results and hosted URLs in `docs/validation.md`. No item is complete
without its acceptance evidence. External writes retain repository authorization
requirements; this document creates no GitHub issues, releases, or mutations.

## Proposal-artifact validation

On the documentation-only working tree above baseline `185f311`, the full suite
passed 171 tests (97.178 seconds), CLI help and bundled plugin validation passed,
and documentation links/anchors, roadmap ID uniqueness/coverage (R01-R20), and
`git diff --check` passed. No skill or runtime files changed, so no changed-skill
validation was required. An initial ID-coverage check used unpadded IDs; correcting
the check to compare numeric IDs passed without changing the roadmap identifiers.
At the proposal-only checkpoint, no hosted workflow, remediation regression, new release, or cleanup was run. Subsequent R14 implementation evidence is recorded in [validation.md](validation.md#r14-corrective-implementation-local-evidence).
