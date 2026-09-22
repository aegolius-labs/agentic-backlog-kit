# Adoption relationship inference, live validation 2026-09-22

GH-63 shipped in `v0.7.0` verified by unit tests only. Every issue in this
repository already carries the kit's marker, so `read_unmanaged` returns nothing
here and there was nothing to point inference at. This records the live run that
closed that gap, and the two things it found.

## The fixture

`aegolius-labs/abk-adopt-eval-20260922`, private, created 2026-09-22 and
**retained**. The authenticated token has no `delete_repo` scope, so this
evaluation could not remove it. Cleanup is one deletion by a token that has that
scope, or through the web UI. Its identity is recorded here rather than left to
be rediscovered, which is the whole content of R20.

Ten issues, typed by `type:` label so the fixture does not depend on the
organization's native issue-type configuration:

| Issue | Type label | Adopts as | Parent | Blocked by | Exercises |
| --- | --- | --- | --- | --- | --- |
| #1 | `type:epic` | Epic | - | - | root |
| #2 | `type:feature` | Feature | #1 | - | parent one level above |
| #3 | `type:story` | Story | #2 | - | parent one level above |
| #4 | `type:task` | Task | #3 | #3 | parent and dependency on one issue |
| #5 | `type:story` | Story | #1 | - | parent skipping a level |
| #6 | `type:chore` | Task | #2 | - | alias type, parent two levels above |
| #7 | `type:story` | Story | - | #8 | dependency |
| #8 | `type:story` | Story | - | - | intended cycle partner |
| #9 | *(none)* | Task | - | #1 | untyped default, cross-level dependency |
| #10 | `type:task` | Task | #3 | - | added after adoption, for orphan recovery |

## What was verified

**Inference proposes the structure GitHub records.** The flat plan produced nine
items with `parent: null` and `depends_on: []`. The same plan with
`--infer-relationships` produced three parents (`GH-2 -> GH-1`,
`GH-3 -> GH-2`, `GH-4 -> GH-3`) and three dependencies (`GH-4 -> GH-3`,
`GH-7 -> GH-8`, `GH-9 -> GH-1`). The digests differ, as they must.

**A cross-level dependency is allowed.** `GH-9` is a Task depending on `GH-1`,
an Epic. Dependencies carry no level rule and none was invented.

**Both hierarchy withholdings fired, with accurate reasons.**

```
GH-5: parent: 'GH-1' is type 'Epic' and this item is type 'Story',
      which the hierarchy does not allow
GH-6: parent: 'GH-2' is type 'Feature' and this item is type 'Task',
      which the hierarchy does not allow
```

**A narrowed adoption withholds outside references but keeps internal ones.**
`--include 3 --include 4` proposed `GH-4 -> GH-3` for both parent and
dependency, and withheld `GH-3`'s parent with
`issue #2 is neither managed nor part of this adoption`.

**The orphan reason and its recovery path work end to end.** With `GH-3` removed
from the manifest while its marker stayed on GitHub, planning `#10` reported
`orphans: ["GH-3"]` and withheld its parent with
`issue #3 is marked as 'GH-3' but the manifest does not record it; run
import-reconcile first`. After `import-reconcile`, re-planning proposed
`GH-10 -> GH-3` with nothing withheld.

**Apply and idempotence.** `import-apply` completed 9/9 against the reviewed
digest; a second plan proposed zero items.

**The manifest agreed with the repository.** Immediately after apply, seven of
nine items matched GitHub's parent and dependency structure exactly. The two
that did not were `GH-5` and `GH-6` - the deliberate, reported withholdings.
Before this change all nine would have disagreed silently, because
synchronization is additive and never removes the relationships GitHub still
holds.

## What this found

### F1 - GitHub refuses to create a dependency cycle

**Owner:** GH-63. **Status:** not a defect; it narrows a claim.

Seeding `#7 blocked by #8` and `#8 blocked by #7` was rejected by GitHub:

```
422 Validation failed: this dependency would create a cycle where the target
    is already blocked by the source
```

So the cycle-withholding branch cannot be reached through GitHub's own
`blocked_by` graph. It is not dead code - it still fires when a dependency
resolves onto an already-managed manifest item whose existing `depends_on`
closes a loop - but its trigger is narrower than the design assumed, and it
remains covered by unit tests rather than by this run.

This is worth stating plainly: a live evaluation that silently failed to
exercise a branch, and reported success anyway, would be worse than no
evaluation.

### F2 - `import-reconcile` recovers an orphan flat

**Owner:** new item, filed against R11. **Status:** open.

Recovery records a stranded marker under the id GitHub already uses, with
neutral defaults and no relationships - including when GitHub records a parent
and dependencies for that issue. `GH-3` came back with `parent: null` despite
GitHub holding `#3 -> #2` throughout.

That is exactly the divergence GH-63 removed from adoption, still present in the
recovery path: additive synchronization will never reconcile it, so a recovered
item disagrees with its own repository permanently and silently. Adoption is now
honest about structure and recovery is not.

## Limits of this run

- The fixture is synthetic and small. It says nothing about request cost or
  rate limits on a repository with hundreds of unmanaged issues.
- Issue types were expressed as `type:` labels. The native-issue-type path
  through `_resolve_type` was not exercised here.
- No Project exists for the fixture, because adoption never reads or writes one.
  `sync-plan` was therefore not run against it, and convergence was verified by
  comparing the manifest to GitHub's structure directly.
- `GH-4` appears to disagree with GitHub in the final state of the fixture. That
  is an artifact of this evaluation, not of the product: stranding `GH-3` for the
  orphan test also cleared the references to it that `GH-4` held. `GH-4` adopted
  correctly, with parent and dependency both proposed, as the state recorded
  immediately after the first apply shows.
