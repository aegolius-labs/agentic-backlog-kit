# Operational authority (R15)

GitHub owns what is happening to a piece of work. The manifest owns what the
work is and why it matters. This note states where the line falls, what changed
for manifests written before it, and what offline planning can and cannot tell
you.

## The line

| Field | Owner | Why |
| --- | --- | --- |
| `Status` | GitHub, once the item exists there | What is happening now is an observation |
| `Sprint` (the iteration field) | GitHub, once the item exists there | Commitment is an observation about a team |
| `Impact`, `Effort`, `Business Value`, `Enabler Value` | The manifest | These are judgements about the work |
| `Priority` | Computed | Derived from the judgements and fresh operational state |
| Title, body, type, parent, dependencies | The manifest | These describe what the work is |

This is decision **D1**. It follows from the authority model the three Aegolius
Labs repositories share: downstream state flows back as evidence, never as
intent. A closed issue or a moved card is an observation. It informs what to do
next. It is not an edit to what should be built, and the reverse is equally
true - local intent does not get to overwrite an observation.

## What ordinary synchronization does now

`sync-plan` no longer plans a `Status` or `Sprint` write for an item GitHub
already tracks in the Project. If someone moves a card to `In Progress`, the
next sync leaves it there.

Two cases still write operational fields:

- **A new item.** The first time an item is projected, it carries the
  manifest's `status` and `sprint`. There is no remote observation to defer to
  yet.
- **An item not yet in the Project.** Same reasoning: adding it to the Project
  is its first projection.

## Moving operational state deliberately

When local intent genuinely should win - reopening work, correcting a mistake,
committing an item to a sprint - use an explicit transition:

```bash
abk sync-plan --transition R15="In Progress"
abk sync-plan --transition-sprint R15="Sprint 4"
```

A transition is not a special mutation. It writes the same Project field any
other update writes. What makes it a transition is that it is named on the
command line, recorded in the plan, folded into the plan digest, and bound to
the value that was observed at planning time:

```json
{
  "kind": "project.transition",
  "item_id": "R15",
  "payload": { "fields": { "Status": "In Progress" } },
  "precondition": { "observed": { "Status": "Ready" } }
}
```

If anyone changes that field between planning and apply, the plan no longer
matches fresh state and apply refuses before writing anything. Recovery is the
same as everywhere else in the kit: build a new plan, review it, confirm it.

A transition also carries its own derived consequences. Moving an item to a
done status changes its computed `Priority`, so the plan sets that too and one
apply settles. A plan should describe the state it intends to leave behind; a
plan that scored only the state it found would need a second sync to settle the
priorities it had just invalidated.

A transition is rejected before planning when it names an unknown item, a
status outside `workflow.statuses`, a field other than `Status` or the
iteration field, an unresolved `@current` / `@next` alias, or an item GitHub
does not yet track. A transition that matches what GitHub already reports plans
nothing.

## Planning against fresh state

Ranking and sprint selection ask what to do next, which depends on what is
happening now. Pass a snapshot to answer that from GitHub:

```bash
abk snapshot --output .agentic-backlog/snapshot.json
abk next --operational-snapshot .agentic-backlog/snapshot.json
abk prioritize --operational-snapshot .agentic-backlog/snapshot.json
abk sprint-plan --operational-snapshot .agentic-backlog/snapshot.json
```

Every planning command reports which state it used:

```json
{ "operational_state": "github" }
{ "operational_state": "local-intent" }
```

Add `--report-operational-drift` to see exactly what differed.

### Offline preview is a preview

Without `--operational-snapshot`, planning uses the manifest. That is supported
and it is the default, because planning must work without network access. It is
a preview, not an answer:

- Work finished on the board still looks open, so `next` can hand an agent
  something already done.
- A completed prerequisite still boosts the work that depends on it, so the
  ranking is inflated.
- Sprint occupancy reflects intent rather than commitment.

The `operational_state` field says which of the two you are reading. Treat
`local-intent` as provisional whenever the board has other contributors.

### A remote status the manifest does not define

Scaffolding appends the manifest's statuses to the ones GitHub already offers,
so a board legitimately carries statuses the manifest has never heard of -
GitHub's default `Todo`, for one. Such a status is **reported but not adopted**:
scoring and sprint rules are written in the manifest's vocabulary, and importing
a foreign value would hand those rules something they cannot reason about.

`--report-operational-drift` shows these with `"applied": false` and a reason.
To adopt one, add it to `workflow.statuses` first.

## Migrating a manifest written before D1

Nothing breaks and no schema change is required. `status` and `sprint` remain
required fields, because they are still the values a new item is created with.

What changes is what they mean for an item that already exists on GitHub: they
become the value the item *started* with, not the value the kit will keep
enforcing. Concretely:

1. **Expect your first post-upgrade `sync-plan` to be smaller.** Operational
   differences that used to generate `project.set_fields` actions no longer do.
   That is the fix, not a missing action.
2. **Stop editing `status` in the manifest to drive the board.** It will not
   take effect for existing items. Use `--transition`.
3. **Let the manifest's `status` drift.** For long-lived items it will fall out
   of date, and that is correct - GitHub holds the current value. Read current
   state with `--operational-snapshot` rather than trying to keep the manifest
   in step by hand. There is no command that writes observed state back into
   the manifest, and that is deliberate for now: it would reintroduce the
   question of which copy is authoritative.
4. **Add any board statuses you want planning to honour** to
   `workflow.statuses`, or they will be reported and ignored.

## Sprint commitments

R16 builds on this. Once GitHub owns `Sprint`, replanning must not undo what
that field records, so `sprint-plan` retains work already committed to the
target sprint and withholds work committed elsewhere unless it is explicitly
carried over. See [sprint commitments](sprint-commitments.md).

## Edits made on GitHub

Title and body are the manifest's to own (see the table above), but that
authority only ever pointed one direction as far as a machine could tell: if a
teammate edited a managed issue's title or body directly on GitHub, the next
`sync-plan` proposed reverting it, and confirming that plan silently undid the
human's edit. R35 (2026-09-28) closes that gap by giving the kit a way to tell
"the manifest changed" apart from "a human edited GitHub".

**The baseline comment.** Title and body are held independently, because in
`--preserve-body` mode the kit still owns the title while a human is expected
to freely edit the body - a single combined digest could not tell those apart
without either missing a held title or falsely holding an ordinary body edit.
So whenever the kit writes an issue's title and/or body - on `issue.create`,
and on `issue.update` whether the body is fully managed or only its identity
marker is - it appends a second hidden comment, after everything else in the
body, carrying one digest per field:

```
<!-- agentic-backlog-kit:written=v1;title=<16 hex chars>;body=<16 hex chars> -->
```

The title digest covers the exact title being written; the body digest covers
the exact body content being written (this comment itself excluded) - both
after normalizing line endings and trailing whitespace, so a GitHub-side
CRLF/LF change alone never looks like an edit. This is separate bookkeeping
from the identity marker (`agentic-backlog-kit:id=...`) - the two never
overlap, and the identity marker byte layout does not change. The comment is
parsed defensively: an unrecognized version or anything malformed is treated
as no baseline at all, the same as an issue that was never written this way.

**Detection, per field.** The next `sync-plan` recomputes each field's digest
from the remote issue's *current* title and body content and compares it with
the digest the remote's comment still carries for that field:

- **Matches** - that field is exactly as the kit left it. Any difference from
  the manifest is planned as an ordinary part of `issue.update`, same as
  before.
- **Does not match, and the field now differs from what the manifest
  wants** - a human changed it since the kit's last write. That field is
  **held**: it is left out of the plan and reported instead, under
  `held_remote_edits`, naming only the fields actually held:

  ```json
  {
    "item_id": "R35",
    "issue_number": 214,
    "fields": ["title"],
    "reason": "edited on GitHub since the kit last wrote it",
    "hint": "Update the manifest item to accept the GitHub edit, or pass --overwrite-remote-edit R35 to restore the manifest's version"
  }
  ```

  A field that is not held is still planned - a held title does not stop an
  unheld body update, and vice versa. Type, label, and Project field actions
  for the same item are unaffected either way.
- **Does not match, but the field already equals what the manifest
  wants** - nothing to do for that field: no hold, no action.
- **No baseline for that field** (comment missing or unreadable) - every
  issue written before this feature falls here for both fields. The kit
  behaves exactly as it did previously: the field is planned, and the next
  write that touches this issue installs a baseline for it.

When only one field is held and the other is being written anyway, the body
still has to be rewritten to keep the held field's own digest legible: it is
carried forward unchanged as the field's own *recorded* digest rather than
refreshed to the field's current remote value. Concretely, if the body is
held but the title is being renamed, the write keeps the human's body content
untouched and keeps the *old* recorded body digest, so the body still reads
as held on the next plan instead of the rename silently adopting the human's
edit as a new baseline; symmetrically, if the title is held but the body is
being updated, the write keeps the human's title untouched and keeps the old
recorded title digest.

`--preserve-body` never holds the body: the kit only ever touches the
identity marker there, never arbitrary prose, so there is no kit-managed
content for a human edit to conflict with. Its title is held on the same
terms as a managed body's.

Held edits are folded into the plan digest, so a plan reviewed with one held
field cannot later be silently re-confirmed against a plan without it.

**Overriding a hold.** Once you have looked at the GitHub edit and decided the
manifest's version should win anyway:

```bash
abk sync-plan --overwrite-remote-edit R35
```

repeatable per item, and it overrides every field currently held for that
item (not just one of them). It is rejected before anything is planned if the
named item does not exist or has nothing held. Applying the resulting plan
writes a fresh baseline for whatever it overwrote.

**Adopting the human edit instead** is not a command - the manifest is edited
by a person - but it is the usual path: update the manifest item's title or
description to match what is now on GitHub, and the next plan finds nothing
to hold for that field.

**Migration note.** An issue the kit wrote before 2026-09-28 has no baseline
comment yet. Nothing breaks: the first `sync-plan` after upgrading plans its
title/body exactly as it would have before, and the write that applies it
installs the issue's first baseline. From then on, an edit made directly on
GitHub is detected and held. There is no mass rewrite to backfill a baseline
onto every existing issue at once, and that is intentional - an issue nobody
is touching stays untouched, and the baseline arrives the same way every other
correction does, as a side effect of the kit's next legitimate write to it.

**Known limit: deleting the comment.** The baseline lives entirely inside the
issue body, so a person who deletes that hidden comment (deliberately or by
overwriting the whole body) removes the baseline along with it. The next
`sync-plan` then reads that field as never having a baseline at all: it plans
the update exactly as it would for an issue written before this feature, and
that write installs a fresh one. This is visible in the plan, not a silent
loss - there is simply nothing left for the kit to compare against, the same
as any other issue mid-migration.

## Known limits

- Composition reads `Status` and the iteration field only. Assignees, labels
  outside the type label, and other Project fields are not yet composed.
- Composition reads fields, not people: who is assigned to an item is not part
  of operational state yet.
- There is no way to write observed operational state back into the manifest.
  Offline planning therefore stays as stale as the manifest is, and the only
  remedy is to pass a snapshot.
