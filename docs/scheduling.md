# Projecting a schedule

```bash
abk gantt                                   # Markdown, chart plus its basis
abk gantt --format mermaid                  # just the chart block
abk gantt --format json --output plan.json  # machine-readable schedule
```

## What the projection is

A schedule here is derived entirely from what the manifest already carries:

| Input | Comes from |
| --- | --- |
| Duration | `effort` x `--days-per-effort` (default 2) |
| Order | the `depends_on` graph, which is already proven acyclic |
| Tie-break | computed priority, so the ranked head schedules first |
| Concurrency | `--lanes`, how many items may run at once |
| Day zero | `--start`, else `workflow.iteration.start_date` |
| Grouping | each item's immediate parent |

It is deterministic. The same manifest, start and options always produce the
same schedule, which is what lets it be regenerated and diffed rather than
maintained by hand.

## What it is not

**It is a projection, not an estimate.** There is no velocity history, no
per-person assignment, and no calendar of working days behind the dates. It says
exactly what the dependency graph and the effort points imply, and nothing more.
Read a bar as "this much effort, in this order", not as a delivery date.

Effort points are an ordinal 1-5 scale. Multiplying them by a constant is a
declared convention, not a measurement, which is why the factor is printed on
every chart rather than hidden in a default.

## What is left out, and why

- **Completed work**, by default. It has no remaining duration, so drawing it
  would spend chart width on time already gone and push everything after it.
  `--include-completed` draws it as `done` if you want the full arc.
- **Containers that have children.** An Initiative, Epic or Feature groups the
  work its children carry, and scheduling both would double-count. A container
  with *no* children is scheduled, because nothing else represents it - without
  that, a roadmap of undecomposed features projects to an empty timeline.

Every exclusion is reported with its reason under `excluded`, so nothing is
dropped silently.

## Lanes

One lane is a single worker and produces the honest serial projection. More
lanes let independent work run in parallel and shorten the chart. **Lanes never
reorder a dependency** - they only decide how much unrelated work runs
alongside. Raising the lane count to make a date look better is measuring the
lane count, not the work.

## The critical path

The longest chain of scheduled dependencies, which is what actually sets the
finish date. Only scheduled work counts: a chain running through work the
projection excluded would describe a timeline the chart does not draw.

## Rendering

The Markdown and Mermaid formats emit a `gantt` block, which GitHub renders
natively in Markdown. Mermaid is text, so the kit stays dependency-free and the
chart stays diffable.
