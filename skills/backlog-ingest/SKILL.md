---
name: backlog-ingest
description: Capture an idea, request, defect, or implementation need as one validated Agentic Backlog Kit item, or refine an existing item. Use for ideation and backlog ingestion; do not use for bulk GitHub reconciliation or sprint selection.
---

# Ingest backlog work

Keep model context bounded: use `summary` and targeted `show ITEM_ID`; do not load or restate the full manifest unless the requested change genuinely needs it.

1. Locate the plugin root and run `python <plugin-root>/scripts/backlog.py validate`.
2. Classify the request at the smallest honest layer: Initiative, Epic, Feature, Story/Bug, or Task. Preserve the direct-parent hierarchy.
3. Identify outcome, acceptance criteria, parent, dependencies, Impact, Effort, Business Value, Enabler Value, status, and maturity. Ask only when a missing value would materially change the item. Record uncertain early work as `maturity: idea` or `refined`; never invent readiness.
4. Use `show` for proposed parent and dependency IDs. Do not create guessed references.
5. Write one compact item or patch JSON under `.agentic-backlog/cache/`, then call `item-add` or `item-update`. Let the engine generate an ID when adding unless the user supplied a stable ID.
6. Run `validate` and `show` for the resulting ID. Do not sync to GitHub unless requested.

Read [references/item-contract.md](references/item-contract.md) for field semantics and classification boundaries.

Return the stable ID, type, maturity, parent/dependencies, scores supplied, and whether GitHub synchronization remains pending.
