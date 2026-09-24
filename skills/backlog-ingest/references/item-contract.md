# Item contract

Classification:

- Initiative: strategic outcome spanning epics.
- Epic: large outcome spanning features.
- Feature: cohesive user-visible capability.
- Story: user-centered, independently demonstrable slice.
- Bug: defect or regression at the Story layer.
- Task: implementation or operational work beneath a Story or Bug.

Scoring inputs are integers. Impact, Effort, and Business Value range from 1 to 5; Enabler Value ranges from 0 to 5. Enabler Value measures how strongly the item unlocks other delivery, architecture, compliance, or operational work.

Maturity:

- `idea`: captured but ambiguous; acceptance criteria may be empty.
- `refined`: understood but not ready to schedule.
- `ready`: has at least one verifiable acceptance criterion and sufficient planning inputs.

Commands:

```text
python <plugin-root>/scripts/backlog.py summary
python <plugin-root>/scripts/backlog.py show ITEM_ID
python <plugin-root>/scripts/backlog.py item-add --input .agentic-backlog/cache/item.json
python <plugin-root>/scripts/backlog.py item-update ITEM_ID --input .agentic-backlog/cache/item-patch.json
python <plugin-root>/scripts/backlog.py validate
```

Optional canonical GUID:

- `guid` links an item to the aio-agentic-sdlc Intention DAG node it projects. Supply it only when that framework hands the work over; standalone use owns no Intention DAG and leaves it out.
- It must be a canonical lowercase UUID exactly as `str(UUID(value))` renders it, unique across the manifest, and it needs `schema_version` 2. The kit reads version 1 manifests and writes them back as version 2.
- Never invent one. A GUID that points at no Intention DAG node is worse than none.

An add payload contains every item field except `id`, which may be omitted for deterministic generation, and the optional `guid`. An update payload contains only changed fields and cannot change `id`.

