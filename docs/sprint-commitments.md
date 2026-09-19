# Sprint commitments and carryover (R16)

A sprint is a promise about a period of time. Once [GitHub owns the iteration
field](operational-authority.md), replanning must not quietly undo what that
field records. This is decision **D2**, carryover policy **A**.

## The rule

Planning a specific sprint partitions the backlog three ways:

| Partition | Meaning | What planning does |
| --- | --- | --- |
| **Retained** | Already committed to the target sprint | Counted once against capacity, reported separately, never re-selected |
| **Committed elsewhere** | Assigned to a different sprint | Withheld from automatic selection, offered as carryover |
| **Unassigned** | Committed to nothing | Selected normally, by priority and capacity |

Completed work is in none of them. It neither occupies the sprint nor needs
carrying over.

## Retained work

Work already in the target sprint keeps its place. It consumes capacity once,
and it keeps whatever status it has reached:

```json
{
  "retained": [
    { "id": "A", "title": "...", "type": "Story", "status": "In Progress", "effort": 3 }
  ],
  "retained_effort": 3,
  "committed_effort": 5,
  "remaining_capacity": 3
}
```

An item that is `Blocked` or not yet `ready` still occupies the sprint if it was
committed to it. That is deliberate: it is in the sprint, so it is costing the
sprint something, and hiding it would make capacity look better than it is.

Retained entries are projected compactly - id, title, type, status, effort.
The ranking detail that justifies a *new* selection adds bytes without adding
an answer for work that is already committed.

### Overage

If commitments already exceed capacity, planning says so rather than silently
dropping work:

```json
{ "capacity": 6, "retained_effort": 10, "overage": 4, "items": [] }
```

Nothing new is selected, and `overage` is the amount the sprint is over. The
remedy is a person's decision, not the planner's.

## Work committed elsewhere

The highest-scoring item in the backlog is not selected if it is committed to
another sprint:

```json
{ "carryover_available": { "B": "Sprint 2" } }
```

Pulling it automatically would break somebody else's sprint to improve this
one's ranking. It is reported once, with the sprint that holds it - not also
repeated in `skipped`, which would double a list that grows with the backlog.

To move it, name it:

```bash
abk sprint-plan --sprint "Sprint 1" --carryover B
```

It then competes for capacity like any other candidate, and the plan records
that it was carried over:

```json
{ "carryover_selected": ["B"] }
```

A carryover request is rejected before planning when it names an unknown item,
work that is already complete, work already committed to the target, work
committed to no sprint at all, or when no target sprint was given.

## Planning without a target

`sprint-plan` with no `--sprint` ignores sprint assignment entirely and ranks
the whole backlog, exactly as it did before this policy. Commitment is relative
to a target: with no target there is no sprint to protect and no "elsewhere" to
withhold from. `--carryover` without `--sprint` is rejected rather than
silently ignored.

## Keeping output bounded

`--skipped-limit N` projects `skipped`, `retained` and `carryover_available`,
each with a count and a truncation marker:

```json
{
  "retained_count": 30, "retained_truncated": true,
  "carryover_available_count": 30, "carryover_available_truncated": true
}
```

On a large backlog every one of those lists grows with the backlog while the
decision stays small. Without the limit a 10,000-item plan is roughly 555 KB;
with it, roughly 8 KB.

## Use fresh state

Retention and carryover are only as good as the sprint values they read. Local
intent is stale by design under D1, so pass a snapshot:

```bash
abk snapshot --output .agentic-backlog/snapshot.json
abk sprint-plan --sprint "Sprint 1" --operational-snapshot .agentic-backlog/snapshot.json
```

The plan reports `"operational_state": "github"` when it did. Without it,
retention reflects what the manifest last recorded rather than what the board
says, which on a shared board is a preview rather than an answer.

## Known limits

- Capacity is effort-based and team-wide. Per-assignee capacity is not modelled.
- Carryover moves work *into* the plan being built. It does not remove the item
  from its previous sprint; that is a `--transition-sprint` on the next sync.
- An item retained while `Blocked` still consumes capacity. There is no
  automatic recommendation to drop it.
