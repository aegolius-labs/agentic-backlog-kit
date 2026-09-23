---
name: backlog-prioritize
description: Rank an Agentic Backlog Kit manifest, select its next executable item with the reasons it passed others over, or project the backlog onto a timeline as a Gantt chart, using deterministic Impact, Effort, Dependency, Enabler, and Business Value scoring. Use for prioritization, sequencing, scheduling, and answering what to work on next; not for subjective re-scoring without evidence.
---

# Prioritize backlog work

1. Locate the plugin root and run `python <plugin-root>/scripts/backlog.py validate`.
2. Run `prioritize --limit N` for a ranked slice or `next` for one executable item. Keep the slice as small as the request permits.
3. Prefer fresh operational state. Without `--operational-snapshot`, ranking and selection use local intent, which lags what GitHub now says; the result labels itself `"operational_state": "local-intent"` when that happens, so read that field before reporting an answer as current.
4. Report what `next` passed over. `--explain N` returns the higher-ranked items that were not selected, each with its reason — unrefined, waiting on a named dependency, explicitly blocked, or a container whose children carry the work. Report those alongside the selection, because a selection nobody can audit cannot be picked up by whoever comes next.
5. Treat engine output as the deterministic result. Do not reorder by intuition. If the ranking looks wrong, inspect the affected items with `show`, explain which input or dependency causes it, and propose a manifest update.
6. Never assign missing scores or dependencies silently. Use `$backlog-ingest` when refinement is required.
7. Use `gantt` when the request is about sequence over time, a roadmap view, or a chart. Read [references/scheduling.md](references/scheduling.md) first, and state the basis with the chart: durations are effort points times one declared factor, order is the declared dependency graph, and there is no velocity history behind the dates. Never present it as a delivery estimate, and never raise `--lanes` to make a date look better — that measures the lane count, not the work.

Default base score is `Impact*2 + BusinessValue*2 + EnablerValue + (6-Effort)`. Each prerequisite receives 25% of each direct dependent's final score. The final list is dependency-valid; completed items score zero, and blocked or unrefined items are not returned by `next`.

Report IDs, concise titles, base/final scores, material dependency effects, the next executable item, and what it passed over. This workflow does not mutate GitHub.
