# Active task handoff

The user transferred continuation of **Create agentic backlog kit** into
**Review project roadmap** and approved carryover policy A.

## Current activation checkpoint (2026-09-22)

GH-63 shipped in `v0.7.0` and is live-validated against
`aegolius-labs/abk-adopt-eval-20260922`; see
[the validation record](adoption-live-validation-2026-09-22.md). The
`backlog-adopt` skill and structural orphan recovery shipped alongside it, the
latter in `v0.8.0`.

**This file no longer lists what to do next.** Every previous checkpoint here
restated a ranking in prose, the ranking changed, and the prose did not - the
version written earlier today named S-R11-4 as the next work and was wrong
within hours, because S-R11-4 shipped the same day. Ask the kit instead:

```bash
abk snapshot --output .agentic-backlog/cache/remote.json
abk next --explain 5 --operational-snapshot .agentic-backlog/cache/remote.json
abk gantt --lanes 1 --days-per-effort 2
```

`next --explain` returns the selection *and* the higher-ranked items it passed
over with the reason for each, so the answer can be audited by someone who was
not here. [docs/handoff.md](handoff.md) states the rule and why it exists.

What follows is only what the kit cannot compute.

### Decisions the owner still owes

- **R10** cannot start until a removal and reverse-sync authority policy per
  managed field is recorded. Its scope grew on 2026-09-22: recovery repairs only
  the items it recovers, so an already-managed item whose local intent disagrees
  with GitHub stays diverged, and reconciling that direction is R10's.
- **R25** bumps the manifest schema version. Confirm the migration shape before
  starting it.

### Authorization gates

- **R14** hosted draft/partial-upload recovery needs its own authorized
  evaluation against a disposable fixture. Local tests cannot close it.
- **R20** needs refreshed resource identities and a separately confirmed cleanup
  plan. Its scope now includes `aegolius-labs/abk-adopt-eval-20260922`, retained
  because this session's token carried no `delete_repo` scope.

### Standing limitations

- GitHub refuses to create a dependency cycle, so adoption's cycle-withholding
  branch could not be exercised live and rests on unit tests alone.
- The adoption evidence is synthetic and small. It says nothing about request
  cost or rate limits on a repository with hundreds of unmanaged issues.
- Activation cases for `backlog-adopt` are declared, not executed. Running the
  corpus against an installed plugin is its own authorized evaluation.

## Superseded activation checkpoint (2026-09-21)

R15, R16, R11, R22, R23 and R13 have all shipped since the checkpoint below,
which is retained but no longer describes the next work. GH-63 lands adoption
relationship inference: `import-plan --infer-relationships` proposes the
sub-issue parent and `blocked_by` dependencies GitHub already records, withholds
whatever the manifest's hierarchy and acyclic rules cannot express, and reports
why. Suite: 358 tests passing.

## Superseded activation checkpoint (2026-09-18)

The roadmap was re-cut from one flat twenty-item list into release lines, each
counted against its own membership. R17 and R18 are implemented and verified,
completing the `v0.1.1` correctness line in code.

The kit was pointed at its own backlog for the first time (R21). Organization
Project 6 and 50 public issues now project the roadmap, and both scaffold and
sync converge to zero actions. That exercise found a route asymmetry in the
write path - the `gh` CLI route could never fall back from an unavailable native
issue type - which is fixed here, and produced new items R22, R23 and R24. See
[first-use findings](dogfooding-findings-2026-09-18.md).

Suite: 207 tests passing; byte budgets within envelope; the benchmark report
digest is unchanged.

**Next work:** superseded by the 2026-09-21 checkpoint below.

The `Status` and `Sprint` values on Project 6 are currently written from local
intent. That is the R15 defect, accepted deliberately while dogfooding, and it
is the acceptance evidence R15 and R16 need.

## Superseded activation checkpoint (2026-09-13)

Shared PR #4 merged at `9f323e5ef1266f90f6b10c3aa3a595a0f3542ab9`.
ABK PR #2 corrected the shared pin and merged at
`6d8bcc45197b42bddb3d60476235a36eb772e033`. Production no-bump run
[34180532203](https://github.com/aegolius-labs/agentic-backlog-kit/actions/runs/34180532203)
passed with read-only compute and no publication.

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

Plan G completed. H/I stopped with completed merges preserved; a read-only
activation supplement verified I's successful hosted result. J/K created and
merged the fixture but stopped when untagged history produced no release.
L completed the explicitly approved baseline and publication continuation.
Do not replay any completed writes. Exact receipts remain in
`.agentic-backlog/wave-e`.

The user authorized the existing admin bypass for shared PR #4 only. No protection
settings changed. The previously observed aio-agentic-sdlc PyPI path was outside
this work and was not changed or freshly re-audited on 2026-09-13.

This checkpoint supersedes historical recovery notes below. Preserve local
untracked evaluation and validator artifacts.

## Recovered source state (historical)

- Source task: `01a03696-25b8-79d1-a43f-994535e9638b` (not running when inspected).
- Continuing task: `01a06f17-93be-7d83-8ef5-819c71b76f70`.
- Workspace: `aegolius-labs/agentic-backlog-kit`.
- Current branch: `codex/wave-e-org-release-workflow`, baseline `185f311`.
- Wave D: v0.1.0 published at `6a14b70`; local release-closure commit `0b47d81`
  has not been published. Do not repeat initial publication.
- Last source-task instruction: use the organization reusable workflows for
  versioning and release automation. Its R14 implementation is local only.
- The source task requested approval of publication Plan F; no approval of F
  appears in its latest handoff. This task's review found defects in that exact
  candidate. Plan F is superseded for execution by the corrective work, and its
  original JSON/digest is retained unchanged as historical evidence.
- Cleanup Plan E previously stopped after deleting Project #4. The remaining
  resource identities and permissions must be refreshed before any new plan.
  Do not replay E or infer that its completed prefix should run again.

## Current authority and scope

The original project's purpose and organization-workflow requirement remain in
force. This task has completed analysis and remediation-proposal artifacts.
Taking over does not silently publish old plans, weaken protection, or authorize
unreviewed cleanup. Keep local implementation work and any required external
publication gates distinct.

Both product decisions are now approved:

- D1: fresh GitHub Status/Sprint governs existing work; explicit reviewed
  transitions change it. New items retain manifest defaults.
- D2: policy A excludes work assigned elsewhere from automatic sprint selection
  and offers explicit carryover. Existing ongoing status is preserved.

## Next work

Superseded by the 2026-09-22 checkpoint, and deliberately not restated here.
Run `abk next --explain` against a fresh snapshot. See
[docs/handoff.md](handoff.md) for why this file no longer carries a ranking.
