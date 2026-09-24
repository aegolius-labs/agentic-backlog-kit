# Agentic Backlog Kit roadmap projection

**Generated. Do not edit by hand.** Regenerate with `abk gantt --lanes 1 --days-per-effort 2`.

- Projection start: `2026-09-18`
- Projected finish: `2027-02-16`
- Scheduled items: 29
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
    Represent operational changes as explicit digest-bound tr... :S-R15-3, 2026-11-11, 6d
    Document legacy-manifest migration :S-R15-4, 2026-12-19, 2d
    section R11 - Import existing backlogs and support bulk ingestion
    Preview unmanaged issues read-only :S-R11-1, 2026-09-30, 6d
    Assign stable IDs and apply adoption in deterministic bat... :S-R11-2, 2026-10-18, 6d
    Cover adoption in the skills, not only the CLI :S-R11-3, 2026-11-01, 4d
    Recover an orphan with the structure GitHub records, not... :S-R11-4, 2026-12-23, 4d
    section R22 - Report actionable apply failures
    Name the item and rejected field on apply failure :S-R22-1, 2026-10-06, 6d
    Explain an unavailable native issue type :S-R22-2, 2026-10-30, 2d
    section R16 - Preserve sprint commitments and review carryover
    Account for retained target-sprint work exactly once :S-R16-1, 2026-10-12, 6d
    Offer explicit carryover review for work assigned elsewhere :S-R16-2, 2026-11-17, 6d
    section R21 - Run the kit against its own backlog
    Write up first-use friction against the responsible item :active, S-R21-3, 2026-10-24, 2d
    section Planning and handoff - leave a backlog another agent can...
    R26 - Make the next task answerable by the kit rather tha... :active, R26, 2026-10-26, 4d
    R27 - Project the backlog onto a timeline and render a Ga... :active, R27, 2026-11-27, 6d
    section R14 - Adopt organization-managed semantic releases
    Enforce the release baseline prerequisite without auto-ta... :S-R14-1, 2026-11-05, 6d
    Prove hosted recovery after draft creation and partial up... :S-R14-2, 2026-12-31, 6d
    section v0.4.0+ - Reconciliation and reach
    R25 - Carry a canonical GUID through to GitHub for Seam A... :R25, 2026-11-23, 4d
    R13 - Complete native transport parity and decide on a de... :R13, 2026-12-09, 10d
    section v0.1.2 - Apply ergonomics
    R23 - Converge a fresh Project in one scaffold apply :R23, 2026-12-03, 6d
    section R10 - Close the work lifecycle from evidence
    Make agents link PRs to kit issues with closing keywords :S-R10-1, 2026-12-21, 2d
    Recognize Priority-only plans as pre-authorized :S-R10-4, 2026-12-27, 4d
    Propose closing a parent once every child is closed :S-R10-2, 2027-01-12, 6d
    Remove relationships the manifest no longer declares :S-R10-3, 2027-01-18, 10d
    section Unparented
    Infer hierarchy and dependencies when importing existing... :GH-63, 2027-01-06, 6d
    section Unscheduled - portfolio scale
    R24 - Reconsider hierarchy expressiveness for small work :R24, 2027-01-28, 6d
    R12 - Support multi-repository portfolio planning :R12, 2027-02-07, 10d
    section R20 - Resolve remaining disposable evaluation resources
    Refresh disposable resource identities before any cleanup... :S-R20-1, 2027-02-03, 2d
    Delete the four retired evaluation resources under a conf... :crit, S-R20-2, 2027-02-05, 2d
```

## Not scheduled

| Item | Why |
| --- | --- |
| `EPIC-CONT` | type 'Epic' groups work its children carry |
| `EPIC-OPS` | type 'Epic' groups work its children carry |
| `EPIC-PLAN` | type 'Epic' groups work its children carry |
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
| `S-R21-1` | already complete: status 'Done' |
| `S-R21-2` | already complete: status 'Done' |
