# Schedule projection contract

```text
python <plugin-root>/scripts/backlog.py gantt --lanes N --days-per-effort D
python <plugin-root>/scripts/backlog.py gantt --format mermaid
python <plugin-root>/scripts/backlog.py gantt --format json --output .agentic-backlog/cache/schedule.json
```

Everything in the schedule is derived from the manifest:

| Input | Source |
| --- | --- |
| Duration | `effort` x `--days-per-effort` (default 2) |
| Order | the `depends_on` graph, already proven acyclic |
| Tie-break | computed priority |
| Concurrency | `--lanes`; one lane is a single worker |
| Day zero | `--start`, else `workflow.iteration.start_date` |
| Grouping | each item's immediate parent |

Deterministic: the same manifest, start and options always produce the same schedule.

## Say this with every chart

It is a **projection, not an estimate**. No velocity history, no assignment, no working-day calendar. Effort points are an ordinal 1-5 scale, so multiplying them by a constant is a declared convention rather than a measurement — which is why the factor is printed on the chart instead of hidden in a default.

Never present a chart as a delivery date, and never raise `--lanes` to make a date look better. That measures the lane count, not the work.

## Exclusions

Completed work is omitted by default: it has no remaining duration, so drawing it spends chart width on time already gone. `--include-completed` draws it as `done`. A container — Initiative, Epic, Feature — is omitted when it has children, because they carry the work and scheduling both would double-count. A container with no children is scheduled, because nothing else represents it; without that an undecomposed roadmap projects to an empty timeline.

Every exclusion is reported under `excluded` with its reason. Nothing is dropped silently, so report exclusions when they are material to the question asked.

## Critical path

The longest chain of scheduled dependencies, which is what sets the finish date. Only scheduled work counts; a chain through excluded work would describe a timeline the chart does not draw.

## Persisting one

A committed chart must be regenerable and must be regenerated. State the exact command in the file, and treat a chart that no longer matches its manifest as stale rather than as current.
