# Leaving a backlog another agent can pick up

This kit is used across sessions and across agents. Whoever arrives next did not
watch the last one work, so "what is the next task" has to be answerable from
the repository rather than from memory or from prose somebody remembered to
update.

Two things make that true, and one thing repeatedly made it false.

## What the kit answers

```bash
abk next --explain 5 --operational-snapshot .agentic-backlog/cache/remote.json
```

This returns the next executable item **and the higher-ranked items it passed
over, each with the reason**: not refined, waiting on a named dependency,
explicitly blocked, or a container whose children carry the work. A selection
that reports one id and silently drops everything above it cannot be audited by
someone who was not there, and that silence is what made the ranking look wrong
when it was right.

Always pass a fresh operational snapshot. Without one the answer is computed
from local intent, which lags whatever GitHub now says; the result labels itself
`"operational_state": "local-intent"` when that happens, so check that field
before trusting the answer.

```bash
abk snapshot --output .agentic-backlog/cache/remote.json
abk gantt --lanes 1 --days-per-effort 2
```

`gantt` projects the whole backlog onto a timeline, so the next task arrives
with the shape of the work behind it rather than as an isolated id. See
[scheduling](scheduling.md).

## What prose owns

Only what the kit cannot derive:

- **Decisions the owner still has to make**, and which work is blocked on them.
- **Authorization gates** - work that needs an approved evaluation, a disposable
  fixture, or a permission this session does not hold.
- **Standing limitations** - what the evidence does *not* establish.
- **Resource identities** that would otherwise have to be rediscovered.

`task-handoff.md` carries those and nothing else.

## The failure this exists to prevent

Every previous handoff in this repository went stale the same way: it restated a
ranking in prose, the ranking changed, and the prose did not. The 2026-09-22
checkpoint named S-R11-4 as the next work; S-R11-4 shipped in `v0.8.0` the same
day, and the handoff was wrong within hours of being written.

The rule that follows: **a handoff may not restate anything the kit can compute.**
If you find yourself writing an ordered list of what to do next, delete it and
write the command that produces it. A ranking in prose is a copy, and a copy
goes stale.

The same applies to the committed projection. `docs/roadmap-gantt.md` is
generated, and a test fails when it no longer matches the manifest, because a
generated artifact nobody regenerates is worse than none - it reads as current.
