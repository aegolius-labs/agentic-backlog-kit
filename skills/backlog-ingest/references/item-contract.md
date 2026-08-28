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

An add payload contains every item field except `id`, which may be omitted for deterministic generation. An update payload contains only changed fields and cannot change `id`.

