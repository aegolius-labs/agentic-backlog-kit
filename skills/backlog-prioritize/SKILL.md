---
name: backlog-prioritize
description: Rank an Agentic Backlog Kit manifest or select its next executable item using deterministic Impact, Effort, Dependency, Enabler, and Business Value scoring. Use for prioritization and sequencing, not for subjective re-scoring without evidence.
---

# Prioritize backlog work

1. Locate the plugin root and run `python <plugin-root>/scripts/backlog.py validate`.
2. Run `prioritize --limit N` for a ranked slice or `next` for one executable item. Keep the slice as small as the request permits.
3. Treat engine output as the deterministic result. Do not reorder by intuition. If the ranking looks wrong, inspect the affected items with `show`, explain which input or dependency causes it, and propose a manifest update.
4. Never assign missing scores or dependencies silently. Use `$backlog-ingest` when refinement is required.

Default base score is `Impact*2 + BusinessValue*2 + EnablerValue + (6-Effort)`. Each prerequisite receives 25% of each direct dependent's final score. The final list is dependency-valid; completed items score zero, and blocked or unrefined items are not returned by `next`.

Report IDs, concise titles, base/final scores, material dependency effects, and the next executable item. This workflow does not mutate GitHub.
