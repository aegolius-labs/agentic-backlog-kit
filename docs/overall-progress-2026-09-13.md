# Overall progress report — 2026-09-13

## Summary of Actions Taken

**Current phase: Wave E, post-release corrections. Stage: Ongoing.** The initial
product and v0.1.0 release are complete. The approved release evaluation (Plan L)
is now complete as well. The remaining work is substantive product correction,
release edge-case verification, documentation publication and optional cleanup.
The project is not yet “good enough” to close the corrective phase: R15–R18
remain unimplemented, and R14 still has two acceptance gaps.

This report supersedes older status statements in historical evaluation notes.
The roadmap and release/remediation/handoff documents have been refreshed locally;
this refresh has not been committed, pushed or published. GitHub roadmap issues
were not created or transitioned by this turn.

### Completed foundation and initial delivery

| Item | Delivered result | Status |
| --- | --- | --- |
| R01 | Fresh-state-bound plans, drift rejection and partial-action receipts | Complete |
| R02 | Live GitHub CLI and direct API evaluations; verified state and empty second plans | Complete |
| R03 | First-run Project discovery and creation | Complete |
| R04 | Full Project-view comparison; precise conflicts for unsupported grouping/sorting updates | Complete |
| R05 | Iteration discovery, selection and reviewed lifecycle updates | Complete |
| R06 | Installed plugin/skill evaluation with bounded real traces and deterministic corpus | Complete |
| R07 | Public repository, hosted CI, protected main and v0.1.0 release | Complete |
| R08 | Licensing, support, security and release documentation | Complete |
| R09 | Deterministic output budgets at 100, 1,000 and 10,000 items | Complete |

These are completed delivery criteria, not claims of exhaustive testing. R06 used
representative real traces rather than the entire 34-pair live matrix. Generic
GitHub MCP remains insufficient for Projects; CLI and direct API are the verified
routes. Unsupported view updates fail explicitly rather than silently claiming
success. These limitations remain documented.

### Current corrections and ongoing work

| Item | Current state | Remaining work |
| --- | --- | --- |
| R14 — organization releases | Shared PR #4 and ABK PRs #1/#2 merged; no-bump and real immutable publication verified | Explicit missing-baseline guard; hosted draft/partial-upload recovery proof |
| R15 — GitHub authority | Policy D1 approved; implementation proposed | Fresh GitHub Status/Sprint for existing work; preserve ordinary sync; explicit reviewed transitions and migration tests |
| R16 — sprint commitments | Carryover policy A approved; implementation proposed | Retain target-sprint capacity/status; exclude assignments elsewhere; explicit carryover; depends on R15 |
| R17 — deep graphs | Defect confirmed; remediation proposed | Iterative traversal/scoring and 1,200/10,000-node chain/cycle regressions |
| R18 — completed scores | Defect confirmed; remediation proposed | Final zero scores for completed work and correct boost propagation; integrate effective status |
| R19 — accurate public status | Partial: earlier docs published; latest refresh prepared locally | Publish and read back this current status through the protected process |
| R20 — evaluation cleanup | Pending; separate from product release | Fresh identities and explicit cleanup plan, or explicit retention decision |

The existing runtime can still overwrite operational planning fields from stale
manifest intent, mishandle already assigned sprint work, fail on sufficiently deep
dependency chains and give completed prerequisites nonzero scores. Passing the
current suite does not mean those confirmed defects have been fixed.

### Later roadmap

| Item | State and prerequisite |
| --- | --- |
| R10 — destructive/reverse reconciliation | Not implemented; requires explicit per-field/removal policy and R15/R16 correctness |
| R11 — import and bulk ingestion | Not implemented; depends on stable authority, commitments and adoption/migration rules |
| R12 — multi-repository portfolios | Later; single-repository and import/reconciliation contracts must stabilize first |
| R13 — transport parity/MCP decision | Decision open; CLI/direct API work, generic MCP lacks required capabilities; dedicated adapter needs evidence of benefit |

No new answer is needed for D1 or policy A. Both choices are recorded and should
not be reopened during implementation. Cleanup, additional hosted fault-injection
writes and later destructive product behavior retain their separate approval
boundaries.

## Release work: what changed and what was proved

The original shared workflow published a release immediately. ABK needs wheel
and source-archive assets attached and verified before immutable publication.
The extension therefore separates read-only version calculation from an
organization-owned draft → upload → verify → publish path. Existing no-asset
callers are unchanged. ABK has no PyPI stage; aio-agentic-sdlc was reference-only
and its previously observed PyPI path was not changed or re-audited this turn.

The first merged caller used a PR-head pin that Actions could no longer load
after squash merge and branch deletion. ABK PR #2 corrected it to accepted shared
main and added ancestry checks. Production [no-bump run 34180532203](https://github.com/aegolius-labs/agentic-backlog-kit/actions/runs/34180532203)
then passed without release writes.

The first release-bearing fixture run exposed another real issue (R14-F7): with
no stable tag, the upstream version action compares HEAD to itself and analyzes
zero commits. Plan L explicitly added fixture-only v0.0.0 at the tested baseline
and dispatched the unchanged main once. That completed successfully:

- [Workflow run 34781149178](https://github.com/aegolius-labs/abk-release-eval-20260908/actions/runs/34781149178): compute, preflight and shared publisher all passed.
- [Immutable test release v0.1.0](https://github.com/aegolius-labs/abk-release-eval-20260908/releases/tag/v0.1.0): release ID 388026880, exactly two assets.
- Fixture main: `1bba7e6790c410631d562227379b269c5dade6f7`; baseline: `55a6dc3e9616a0e8cd446cf84c78d7fa48328428`.
- Publisher receipt proves draft assets were verified before publication and verified again afterward.
- Downloaded assets matched the same-run inventory by name, size and SHA-256; metadata and isolated wheel installation/CLI passed.
- Production ABK main remains `6d8bcc45197b42bddb3d60476235a36eb772e033`; shared main remains `9f323e5ef1266f90f6b10c3aa3a595a0f3542ab9`. Their protection, immutability and release inventories were freshly verified unchanged before and after.

This proves the ongoing-release happy path with a baseline. It does not fix
untagged first-release behavior or prove hosted failure recovery. The proposed
remediation is a clear no-write missing-baseline error, with tagged and untagged
regressions. Automatic baseline creation is not authorized by that proposal.

## Validation Steps Taken

**This turn:** exact Plan L digest/preconditions; fixture identity and tested main;
protection and immutability; single baseline tag and dispatch readback; captured
workflow/job results; exact artifact IDs and publisher receipt; final two-tag/
one-release inventory; asset download/hash/metadata checks; clean wheel install,
isolated import and `abk --help`; unchanged production readback; local CLI help; bundled plugin validator;
patch whitespace, local documentation links and R01–R20 coverage checks.
Hosted preflight ran the unchanged product suite and package checks successfully.

**Earlier evidence:** 185 ABK tests, 18 shared tests, contract/ancestry checks,
actionlint and package/budget/plugin checks passed. The full local suite was not
rerun for this documentation-only update. No skill or product runtime changed.
Local fake-transport failure tests remain distinct from the pending hosted
failure-recovery evaluation.

The first read-only preflight attempt was denied network access by the sandbox.
It made no external write; the recorded read-only refresh succeeded with network
permission. No release write was retried or replayed.

## User Review Guide

Start with the current-corrections table above. For release evidence, open the
workflow and immutable test-release links. [Validation details](validation.md#r14-hosted-activation-and-immutable-publication-2026-09-13)
record both file hashes. [Remediation plan](remediation-plan.md) contains the
findings, proposed fixes and acceptance criteria; [roadmap](../ROADMAP.md) gives
all dependencies. Local execution evidence is retained under
`.agentic-backlog/wave-e/r14-live-evaluation-receipt-l.json`.

## Next Steps/Phase

1. Complete R14 missing-baseline handling and prepare a bounded hosted recovery
   evaluation, binding exact failure points, expected partial state and the
   original artifact bytes before approval of any new external actions.
2. Implement R15, then R16, using already approved D1/policy A. Coordinate R17/R18
   graph/scoring fixes and run their new regression gates before a corrective release.
3. Publish this documentation refresh through R19. Keep R20 cleanup separate;
   the live release fixture is retained. Historical cleanup left a private
   repository and the API Project/repository; those resource identities were not
   freshly re-audited in this turn and must be rediscovered before deletion.
4. Revisit R10–R13 after corrective contracts stabilize. Do not advance destructive
   reconciliation or import ahead of authority/commitment correctness.

## Completion

- **Initial release:** 6/6 milestones M0–M5 complete — **100%**.
- **Overall listed roadmap:** 9/20 items R01–R20 fully complete — **45%**.
- **Current approved Plan L:** 5/5 actions complete — **100%**.
- **Wave E corrective items R14–R20:** 0/7 fully closed — **0% closed**, with
  substantial partial work in R14 and R19. This is not a claim that no work occurred.

These percentages count completed milestones/items/actions, not elapsed effort,
production readiness or safety approval. No defensible effort-weighted percentage
is available. The original product is delivered; the correction phase is ongoing.

## Runnable handoff

The downloaded fixture wheel was installed in a clean local environment and its
CLI was launched successfully. To repeat the read-only startup check in PowerShell:

```powershell
& 'D:\Documents\GitRoot\aegolius-labs\agentic-backlog-kit\.agentic-backlog\wave-e\l-wheel-install\Scripts\abk.exe' --help
```

Captured output: `.agentic-backlog/wave-e/l-wheel-help.txt`. This finite check
completed; no server was started. It runs the evaluated wheel and does not perform
GitHub mutations or install the Codex plugin skills.
