# Observed-state evidence (R35)

This kit is layer 4 in the Aegolius Labs authority model: a one-way
projection of accepted work onto GitHub Issues and Projects
(`docs/operational-authority.md`, and the normative statement in
`aio-agentic-sdlc/doc/authority-model.md`). `aio-agentic-sdlc` owns the
Intention DAG (what should be built) and the Reality DAG (what is). Until
R35 there was no defined format for handing this kit's view of GitHub back to
that system, or to any other downstream consumer. `abk observe` is that
channel.

## The rule this exists to serve

**Downstream state flows back as evidence, never as intent.** A closed issue,
a moved Project card, or a committed sprint is an observation. It may inform
a Reality DAG, a dashboard, or a report. It must never be treated as an edit
to what should be built, and it is never written back into this kit's own
manifest either - the manifest stays intent-only (decision D1).

## Producing one

```bash
abk observe
abk observe --output .agentic-backlog/observed-state.json
abk observe --offline-snapshot .agentic-backlog/snapshot.json
```

With no flags, `observe` resolves operational state the same way planning
commands do since R35: the auto-refreshed cache when it is fresh and targets
the same owner/repository/project, otherwise a fresh fetch (see
`docs/operational-authority.md`). `--offline-snapshot PATH` uses an exact
snapshot file instead - the observe-time equivalent of `--operational-snapshot`
- and `--backend`/`--max-age` behave as elsewhere in the kit.

## The contract

```json
{
  "contract": "abk-observed-state",
  "contract_version": 1,
  "observed_at": "2026-09-28T12:00:00Z",
  "source": { "tool": "agentic-backlog-kit", "version": "0.2.0", "route": "gh" },
  "target": { "owner": "aegolius-labs", "repository": "example", "project_number": 1 },
  "items": [
    {
      "item_id": "F-SEAM-A",
      "guid": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "issue_number": 42,
      "state": "open",
      "status": "Ready",
      "sprint": "Sprint 4",
      "in_project": true,
      "in_manifest": true,
      "url": "https://github.com/aegolius-labs/example/issues/42"
    }
  ],
  "unmanaged_issue_count": 2,
  "digest": "sha256:4a66a0b97546a4b9b9a8109d3bbbfc51801278c89f30f2eece7c93b873627eac"
}
```

`schemas/observed-state.schema.json` is the normative shape.
`tests/fixtures/seam-a/observed-state.json` pins this exact example so a
counterpart repository (`aio-agentic-sdlc`) can copy it and assert its own
consumer accepts the same document, the same way
`tests/fixtures/seam-a/projected-item.json` already pins the identity half of
the seam.

Field notes:

- **`items`** covers only issues carrying this kit's marker, sorted by
  `item_id`. An issue GitHub tracks that this kit does not manage never
  appears as an item; it is counted in `unmanaged_issue_count` instead.
- **`status`** and **`sprint`** are the Project fields as currently observed,
  and are `null` when the issue is not in the configured Project
  (`in_project: false`) - there is nothing to observe yet, not an empty
  string.
- **`guid`** is the canonical GUID from the issue's marker, when the item
  carries one, else `null`. This is the same identity Seam A already pins.
- **`url`** and **`closed_at`** are included only when the snapshot already
  carries them; `observe` never makes an additional GitHub call to fill in a
  missing one.
- **`digest`** is a `sha256:` hash of the canonical JSON of every other field.
  It lets a consumer detect that two exports actually differ without diffing
  every item by hand.

## Versioning

`contract_version` stays `1` for an additive change - a new optional field
appended to the document or to an item. It bumps only when an existing field
is renamed, removed, or its meaning changes underneath a consumer that has
not been told. A consumer should reject a `contract_version` it does not
recognize rather than guess at a shape it was never shown.

## What this is not

`abk observe` does not write to this kit's manifest, and it is not a sync
mechanism. It has no opinion about what should happen next - that is what
`next`, `prioritize`, and `sprint-plan` are for, reading the same underlying
snapshot. `observe` exists solely to hand that snapshot to a system that owns
a different layer of the authority model, in a shape stable enough to depend
on.
