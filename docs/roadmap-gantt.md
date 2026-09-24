# Agentic Backlog Kit roadmap projection

**Generated. Do not edit by hand.** Regenerate with `abk gantt --lanes 1 --days-per-effort 2`.

- Projection start: `2026-09-18`
- Projected finish: `2027-04-15`
- Scheduled items: 42
- Duration basis: 2 day(s) per effort point
- Parallel lanes: 1
- Critical path: `S-R15-1 -> S-R15-2 -> S-R11-1 -> S-R11-2`

This is a **projection, not an estimate**. Durations come from effort
points multiplied by one declared factor, and order comes from the
dependencies the backlog already declares. There is no velocity history,
no assignment, and no calendar of working days behind these dates.

```mermaid
gantt
    title Agentic Backlog Kit roadmap projection
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section R15 - Respect GitHub operational status and sprint authority
    Compose fresh operational state for planning :S-R15-1, 2026-09-18, 6d
    Preserve remote Status and Sprint during ordinary sync :S-R15-2, 2026-09-24, 6d
    Represent operational changes as explicit digest-bound tr... :S-R15-3, 2026-12-15, 6d
    Document legacy-manifest migration :S-R15-4, 2027-02-11, 2d
    section R28 - Stay within GitHub rate limits at real backlog sizes
    Read parent and dependency relationships in batched GraphQL :S-R28-1, 2026-09-30, 6d
    Retry throttled GitHub requests with bounded backoff :S-R28-2, 2026-10-12, 4d
    Budget API calls per sync at 100, 1,000 and 5,000 issues :S-R28-3, 2026-12-27, 4d
    section R11 - Import existing backlogs and support bulk ingestion
    Preview unmanaged issues read-only :S-R11-1, 2026-10-06, 6d
    Assign stable IDs and apply adoption in deterministic bat... :S-R11-2, 2026-11-09, 6d
    Cover adoption in the skills, not only the CLI :S-R11-3, 2026-12-05, 4d
    Recover an orphan with the structure GitHub records, not... :S-R11-4, 2027-02-19, 4d
    section R29 - Tell GitHub's read-after-write lag apart from real...
    Resolve Project membership from the issue when the item l... :S-R29-1, 2026-10-16, 4d
    Re-read within a bounded window before calling post-apply... :S-R29-2, 2027-01-26, 6d
    section R30 - Install without cloning, and start from a quickstart
    Install from the GitHub marketplace on both hosts, verified :S-R30-1, 2026-10-20, 4d
    Write a quickstart from install to first converged sync :S-R30-2, 2026-11-05, 4d
    section R22 - Report actionable apply failures
    Name the item and rejected field on apply failure :S-R22-1, 2026-10-24, 6d
    Explain an unavailable native issue type :S-R22-2, 2026-12-03, 2d
    section R16 - Preserve sprint commitments and review carryover
    Account for retained target-sprint work exactly once :S-R16-1, 2026-10-30, 6d
    Offer explicit carryover review for work assigned elsewhere :S-R16-2, 2026-12-21, 6d
    section R31 - Re-verify agent behavior on the current release in...
    Re-run the installed-plugin evaluation in Codex on the cu... :S-R31-1, 2026-11-15, 6d
    Run the first end-to-end evaluation in Claude Code :S-R31-2, 2026-11-21, 6d
    section R21 - Run the kit against its own backlog
    Write up first-use friction against the responsible item :active, S-R21-3, 2026-11-27, 2d
    section Planning and handoff - leave a backlog another agent can...
    R26 - Make the next task answerable by the kit rather tha... :active, R26, 2026-11-29, 4d
    R27 - Project the backlog onto a timeline and render a Ga... :active, R27, 2027-01-04, 6d
    section R14 - Adopt organization-managed semantic releases
    Enforce the release baseline prerequisite without auto-ta... :S-R14-1, 2026-12-09, 6d
    Prove hosted recovery after draft creation and partial up... :S-R14-2, 2027-02-27, 6d
    section v0.4.0+ - Reconciliation and reach
    R25 - Carry a canonical GUID through to GitHub for Seam A... :R25, 2026-12-31, 4d
    R13 - Complete native transport parity and decide on a de... :R13, 2027-02-01, 10d
    section Production readiness - usable by a team other than ours
    R34 - Prove it with one outside pilot :R34, 2027-01-10, 6d
    R32 - Test every supported platform and Python version in CI :R32, 2027-02-15, 2d
    section R33 - State what is supported and promise compatibility
    Publish a compatibility policy and 1.0 criteria :S-R33-2, 2027-01-16, 4d
    State supported account types and repository scope up front :S-R33-1, 2027-02-13, 2d
    section v0.1.2 - Apply ergonomics
    R23 - Converge a fresh Project in one scaffold apply :R23, 2027-01-20, 6d
    section R10 - Close the work lifecycle from evidence
    Make agents link PRs to kit issues with closing keywords :S-R10-1, 2027-02-17, 2d
    Recognize Priority-only plans as pre-authorized :S-R10-4, 2027-02-23, 4d
    Propose closing a parent once every child is closed :S-R10-2, 2027-03-11, 6d
    Remove relationships the manifest no longer declares :S-R10-3, 2027-03-17, 10d
    section Unparented
    Infer hierarchy and dependencies when importing existing... :GH-63, 2027-03-05, 6d
    section Unscheduled - portfolio scale
    R24 - Reconsider hierarchy expressiveness for small work :R24, 2027-03-27, 6d
    R12 - Support multi-repository portfolio planning :R12, 2027-04-06, 10d
    section R20 - Resolve remaining disposable evaluation resources
    Refresh disposable resource identities before any cleanup... :S-R20-1, 2027-04-02, 2d
    Delete the four retired evaluation resources under a conf... :crit, S-R20-2, 2027-04-04, 2d
```

## Not scheduled

| Item | Why |
| --- | --- |
| `EPIC-CONT` | type 'Epic' groups work its children carry |
| `EPIC-OPS` | type 'Epic' groups work its children carry |
| `EPIC-PLAN` | type 'Epic' groups work its children carry |
| `EPIC-PROD` | type 'Epic' groups work its children carry |
| `EPIC-UNSCHED` | type 'Epic' groups work its children carry |
| `EPIC-V010` | type 'Epic' groups work its children carry |
| `EPIC-V011` | type 'Epic' groups work its children carry |
| `EPIC-V012` | type 'Epic' groups work its children carry |
| `EPIC-V020` | type 'Epic' groups work its children carry |
| `EPIC-V030` | type 'Epic' groups work its children carry |
| `EPIC-V040` | type 'Epic' groups work its children carry |
| `INIT-ABK` | type 'Initiative' groups work its children carry |
| `R01` | already complete: status 'Done' |
| `R02` | already complete: status 'Done' |
| `R03` | already complete: status 'Done' |
| `R04` | already complete: status 'Done' |
| `R05` | already complete: status 'Done' |
| `R06` | already complete: status 'Done' |
| `R07` | already complete: status 'Done' |
| `R08` | already complete: status 'Done' |
| `R09` | already complete: status 'Done' |
| `R10` | type 'Feature' groups work its children carry |
| `R11` | type 'Feature' groups work its children carry |
| `R14` | type 'Feature' groups work its children carry |
| `R15` | type 'Feature' groups work its children carry |
| `R16` | type 'Feature' groups work its children carry |
| `R17` | already complete: status 'Done' |
| `R18` | already complete: status 'Done' |
| `R19` | already complete: status 'Done' |
| `R20` | type 'Feature' groups work its children carry |
| `R21` | type 'Feature' groups work its children carry |
| `R22` | type 'Feature' groups work its children carry |
| `R28` | type 'Feature' groups work its children carry |
| `R29` | type 'Feature' groups work its children carry |
| `R30` | type 'Feature' groups work its children carry |
| `R31` | type 'Feature' groups work its children carry |
| `R33` | type 'Feature' groups work its children carry |
| `S-R21-1` | already complete: status 'Done' |
| `S-R21-2` | already complete: status 'Done' |
