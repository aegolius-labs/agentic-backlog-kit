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
happening now. Owner decision **R35** (2026-09-28) made that the default:
`next`, `prioritize`, `sprint-plan`, and `gantt` read fresh operational state
automatically, without requiring an operator to remember `abk snapshot` first.
The manifest itself is never written with observations - only the resolution
of what planning *reads* changed.

```bash
abk next
abk prioritize
abk sprint-plan
```

Each of these, with no extra flags, resolves operational state in this order:

1. **`--operational-snapshot PATH`**, if given, is used exactly as that file
   says - unchanged from before R35.
2. **`--offline`**, if given, uses local intent only. No snapshot is read or
   written. This is the previous default, now explicit.
3. **Otherwise (the new default): auto.** A small cache at
   `.agentic-backlog/cache/observed-snapshot.json` (gitignored) is reused when
   it is younger than `--max-age SECONDS` (default 300) and targets the same
   owner/repository/project the manifest declares. Otherwise the command
   fetches a fresh snapshot the same way `abk snapshot` does, uses it, and
   refreshes the cache. `--backend` selects the transport for that fetch, same
   as elsewhere in the kit.

Every planning command reports which state it used, plus how it was obtained:

```json
{ "operational_state": "github", "freshness": { "source": "cache", "observed_at": "2026-09-28T14:03:00Z", "age_seconds": 42 } }
{ "operational_state": "github", "freshness": { "source": "fetched", "observed_at": "2026-09-28T14:03:00Z", "age_seconds": 0 } }
{ "operational_state": "github", "freshness": { "source": "explicit" } }
{ "operational_state": "local-intent", "freshness": { "source": "offline" } }
```

`operational_state` keeps its old meaning and its old two values, so anything
that already reads it is unaffected. `freshness.source` says how that state was
obtained: `cache` (reused), `fetched` (just read), `explicit` (an exact
snapshot file), or `offline`.

Add `--report-operational-drift` to see exactly what differed, same as before.

### A failed auto-fetch fails closed

If the auto-refresh cannot reach GitHub - no `gh` session, no `GH_TOKEN`, a
transport error - planning does not silently fall back to local intent. It
stops with a clear error and a hint to pass `--offline` for a local-intent
preview instead. Stale or wrong answers are worse than an explicit stop; the
kit would rather ask than guess.

### Every write invalidates the cache

`sync-apply`, `import-apply`, `scaffold-apply`, `iteration-apply`, and
`init-apply` delete the cache after a successful apply, so the very next
planning command refetches rather than answering from the state that write
just changed. `abk snapshot` also refreshes the cache as a side effect, since
it reads the manifest's own target anyway.

### Offline preview is a preview

`--offline` is still supported, and it is what planning must fall back to when
there is no network access. It is a preview, not an answer:

- Work finished on the board still looks open, so `next` can hand an agent
  something already done.
- A completed prerequisite still boosts the work that depends on it, so the
  ranking is inflated.
- Sprint occupancy reflects intent rather than commitment.

The `operational_state` field says which of the two you are reading. Treat
`local-intent` as provisional whenever the board has other contributors.

### The manifest can fall behind the board

When operational state comes from a snapshot - cached, fetched, or explicit -
planning also reports `manifest_behind` whenever the snapshot carries a kit
marker (`abk_id`) for an issue the manifest does not know about:

```json
{
  "manifest_behind": {
    "unknown_managed_issues": [{ "item_id": "T-42", "number": 118 }],
    "hint": "Another machine or user may have added items GitHub already tracks. Run `git pull` to pick up a newer manifest, or `abk import-reconcile` to recover them here."
  }
}
```

This is the signature of another machine, session, or user having added
managed items this manifest has not yet absorbed. The key is omitted entirely
when nothing is unknown.

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

## Known limits

- Composition reads `Status` and the iteration field only. Assignees, labels
  outside the type label, and other Project fields are not yet composed.
- Composition reads fields, not people: who is assigned to an item is not part
  of operational state yet.
- There is no way to write observed operational state back into the manifest.
  `--offline` planning therefore stays as stale as the manifest is; the auto
  default and `--operational-snapshot` are the remedy. `abk observe` (see
  [Observed-state evidence](observed-state.md)) is the one sanctioned channel
  for handing observed state to another system, and even that is evidence,
  never intent - it never writes to this kit's own manifest either.
