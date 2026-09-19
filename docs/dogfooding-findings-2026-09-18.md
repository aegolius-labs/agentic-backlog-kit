# First-use findings, 2026-09-18

The kit was pointed at its own backlog for the first time (R21). This records
what that exercise surfaced, against the work item that owns each observation.

The exercise itself converged. Organization Project 6 holds 44 items, the public
repository holds 44 issues with 43 sub-issue links and 38 dependency links, and
both the second scaffold plan and the third sync plan contain zero actions.

## What broke

### F1 - The `gh` route could never fall back from an unavailable issue type

**Owner:** R13 (transport parity). **Status:** fixed in this change.

`sync-apply` stopped at action 31 of 169, after creating 30 issues, with:

```
GitHub API error 1: gh: Validation Failed (HTTP 422)
```

The organization has native issue types `Task`, `Bug`, `Feature`, `Initiative`,
`Theme`, `Epic`, `User Story` and `Tech Story` - but no `Story`. In
`native_or_label` mode an unavailable native type is supposed to fall back to a
`type:` label, and that fallback keys off an HTTP 422.

`gh api` exits 1 for every API failure and leaves the real status only in its
diagnostic text, so `GitHubApiError.status` carried `1` and the fallback could
never fire. The same manifest would have converged on `--backend api` and failed
on `--backend gh`.

This is the most serious finding, because it is a **route asymmetry in the write
path**: the two supported native transports were not interchangeable, which is
precisely the invariant the architecture claims. R02's live evaluation did not
catch it because that evaluation used a manifest whose types all existed
natively, or exercised the API route for the label-fallback case.

The fix normalizes the status for issue create and update only. An unrelated 422
on any other endpoint keeps its exit code and stays fatal, so the deliberate
conservatism protected by the existing near-miss tests is unchanged.

### F2 - Scaffolding a fresh Project needs two applies to converge

**Owner:** R04 (view configuration). **Status:** recorded, not fixed.

The first `scaffold-apply` reported `completed`, 17 of 17 actions. The second
scaffold plan was not empty: it contained three `project.view.update` actions for
`Backlog`, `Kanban` and `Current Sprint`.

`project.view.create` cannot carry a filter, visible-field list, grouping or
sorting, so every created view needs an immediate repair pass. Convergence was
reached only on the third plan.

This is not a correctness defect - the kit does converge, and it never deletes
and recreates a view to work around the API boundary. It is a usability defect:
a `completed` apply that leaves the target unconverged trains the operator to
distrust the status, and a first-run user reasonably expects one scaffold to
finish the job.

### F3 - Generated plans were not ignored by Git

**Owner:** R21. **Status:** fixed in this change.

`.gitignore` covered `.agentic-backlog/cache/`, `evals/`, `receipts/` and
`*.lock`, but not the plan and snapshot files the CLI writes to the root of
`.agentic-backlog/` by default. `init-plan.json` and every subsequent plan showed
up as untracked, one `git add -A` away from being committed. The repository's own
guidance says these are disposable state that must not be committed.

Now only `manifest.json` is tracked there.

## What held up

### F4 - Fail-closed apply and replan recovery worked exactly as specified

**Owner:** R01.

The failed apply stopped on the first failure, wrote no further mutations, and
journaled 30 completed actions with the exact failing action and its
precondition. Recovery needed no special-case tooling: a fresh `sync-plan`
observed the 30 existing issues and planned only the 14 remaining creates.
Nothing was double-created.

This is the part of the design that earned its complexity.

### F5 - Per-type native/label resolution is correct once the status is right

**Owner:** R13.

After F1, the final state is exactly the intended mixture: native issue types for
the 31 items whose types the organization defines (1 Initiative, 8 Epic, 21
Feature, 1 Bug) and the `type:story` label for the 13 items whose type it does
not. The decision is per item, not a global mode switch.

### F6 - The R18 fix is confirmed on real data

**Owner:** R18.

All 13 completed items score exactly zero and none appears in the ranked head.
Sprint planning selected `S-R15-1` and `S-R15-2` first, which is independently
the work this roadmap identifies as next.

## What was awkward

### F7 - Apply failures are not diagnosable

**Owner:** new item R22.

`GitHub API error 1: gh: Validation Failed (HTTP 422)` names no item, no field
and no reason. Diagnosis required reading the receipt for the failed action,
querying the organization's issue types by hand, and then reading the transport
source. A first-run user would have no path from that message to "your
organization has no `Story` issue type".

The receipt is good - it records the exact failing action and payload. The error
text that reaches the operator is not.

### F8 - A `Task` cannot hang off a `Feature`

**Owner:** new item R24, unscheduled.

The hierarchy is a strict ladder: `Initiative -> Epic -> Feature -> Story/Bug ->
Task`. A parent must be exactly one level above its child, so a small chore
directly under a Feature has no type: `Task` is reserved for level 5 under a
`Story` or `Bug`. Six decomposed items here were written as Tasks and had to be
retyped as Stories, which overstates them.

This may be intentional. It is recorded rather than scheduled.

### F9 - Status options are appended, never reconciled

**Owner:** R10 (destructive reconciliation).

Scaffolding added the manifest's statuses to GitHub's defaults rather than
replacing them, so the Project carries a `Todo` status that the manifest does not
know about. This follows directly from synchronization being additive and
update-only, and it is the safe default. It does mean a scaffolded board can
offer statuses the kit will never plan toward, which belongs in R10's field
authority policy.

### F10 - Ranked output looks unsorted

**Owner:** R09, minor.

`prioritize` returns dependency-topological order, then score - so `S-R15-1` at
41.14 precedes `S-R15-2` at 52.56 because the latter depends on the former. This
is correct and documented behavior, but the JSON carries no indication of why a
lower score outranks a higher one, and the column reads as a sorting bug.

### F11 - A release-bearing merge cannot publish without a hand-written version bump

**Owner:** R14, as R14-F8. **Status:** worked around on 2026-09-18, fixed on 2026-09-19.

Merging the first release-bearing change exercised the organization release
automation for real. `compute-version` correctly derived `v0.1.1` from the
`fix:` commit. Preflight then refused:

```
release check failed: tag 'v0.1.1' does not match package version '0.1.0'; expected 'v0.1.0'
```

No tag, no draft, and no asset were created, and the `release` job was skipped.
The fail-closed contract held exactly as intended, and the repository was left
in a consistent state.

The gap is that nothing synchronizes the packaged version with the computed one.
Publishing required hand-editing five declarations - `pyproject.toml`, both
plugin manifests, the marketplace entry and `__init__.py` - and adding a
CHANGELOG entry. Delegating version calculation to the organization while
requiring a human to predict its answer and write it into five files is not
delegation.

The fix is `scripts/set_version.py`, run by release preflight against the
candidate checkout before building. It stamps the computed version across all
five declarations and promotes the changelog's Unreleased section into that
version's entry. Nothing is committed or pushed, so the tag remains the record
of what a version means and no one has to predict the automation's answer.
The second release-bearing merge hit the same wall before this landed, which
is the argument for fixing a papercut at the source rather than working
around it twice.

Four release tests also hardcoded `0.1.0`, so the bump required editing tests.
Those now derive the expected version from the package, with deliberately
unequal constants where a test needs a genuine mismatch.

### F12 - Adoption marked GitHub before the manifest could record it

**Owner:** R11. **Status:** fixed on 2026-09-19.

The first live adoption wrote the marker to issue #63, then failed before
saving the manifest - `save_manifest` requires an `expected_sha256` the caller
did not pass. GitHub was mutated; the manifest was not.

That left the issue stranded in the one state neither workflow handles: import
skipped it because it was already marked, and synchronization ignored it
because no item claimed it.

The immediate cause was a missing argument. The durable fix is that the state
is now nameable and repairable: `import-plan` reports `orphans`, and
`import-reconcile` records them locally under the ids GitHub already uses,
touching nothing remote because GitHub is already correct.

The ordering cannot be inverted. Writing the manifest first would make
synchronization create duplicates if the GitHub write then failed, which is
worse than a recoverable orphan.

## Evidence

| Artifact | Value |
| --- | --- |
| Project | [aegolius-labs/projects/6](https://github.com/orgs/aegolius-labs/projects/6) |
| Issues created | 44 |
| Sub-issue links | 43 |
| Dependency links | 38 |
| Scaffold convergence | plan 1: 17 actions, plan 2: 3, plan 3: 0 |
| Sync convergence | plan 1: 169 actions (failed at 31), plan 2: 139, plan 3: 0 |
| Suite | 207 tests, all passing |
