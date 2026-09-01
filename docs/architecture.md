# Architecture

## Authority and state

GitHub Issues and an organization-owned GitHub Project are the operational system of record. The tracked `.agentic-backlog/manifest.json` holds only:

- repository and Project identity;
- hierarchy and workflow configuration;
- scoring weights;
- stable agentic backlog IDs;
- desired issue content and planning metadata.

GitHub-owned operational data such as issue numbers, node IDs, Project item IDs, live assignees, and timestamps is discovered on demand. Snapshots, plans, and receipts live under ignored `.agentic-backlog/cache/` and `.agentic-backlog/receipts/` paths.

## Components

1. Focused plugin skills decide which workflow applies and collect only missing judgment inputs.
2. `scripts/backlog.py` exposes concise commands over the local engine.
3. Manifest validation rejects invalid references, hierarchy jumps, duplicate IDs, bad dimensions, and dependency cycles.
4. Scoring and capacity packing are pure local computations; a named sprint commitment additionally requires refreshed iteration identity and lifecycle state.
5. Snapshot readers retrieve only kit-managed issues, marked by `<!-- agentic-backlog-kit:id=...;schema=1 -->`, plus their Project fields, complete managed view configuration, active/completed iterations, and relationships.
6. Reconciliation emits a canonical plan whose SHA-256 digest binds normalized manifest and remote-state fingerprints, planning options, action payloads, and action preconditions.
7. Executors accept only the exact reviewed digest, refresh GitHub, rebuild the plan from the freshly validated local manifest, and abort before mutation on any drift.
8. Apply journals its completed prefix after every action and records the failed action and error on interruption. Resumption always refreshes, replans, and requires confirmation of the new remaining plan rather than replaying the old plan.
9. Skills refresh and re-plan after apply; a successful reconciliation has zero remaining actions.

Project scaffolding preserves the IDs, colors, and descriptions of existing single-select options when extending the built-in Status field. This avoids clearing values already assigned to Project items.

Managed views are compared across layout, filter, ordered visible fields, horizontal and vertical grouping, and ordered sorting. Supported differences become reviewed update actions. Grouping and sorting differences fail closed because the current GitHub view-update input cannot change them safely; the kit does not delete and recreate a same-name view.

Iteration lifecycle plans resolve exact titles, `@current`, or `@next` from canonical active/completed state. A schedule can be extended only from a contiguous, cadence-matching numeric title sequence. GitHub-owned iteration IDs and completion state are bound as preconditions and rechecked after refresh before assignment proceeds.

Native GitHub Projects access is a transport invariant, not an MCP-only feature. A compatible Codex GitHub integration/GitHub MCP, authenticated GitHub CLI, and direct GraphQL/REST API are peer execution routes over the same deterministic engine contract. Capability discovery must prove that a route exposes every operation and identity required by a plan. An incomplete MCP surface is reported and the workflow selects one complete route; writes from different transports are never silently mixed within one apply. The same canonical snapshot, plan, digest, receipt, and post-apply verification contract applies regardless of executor.

## Backlog mapping

| Backlog concept | GitHub representation |
| --- | --- |
| Initiative, Epic, Feature, Story/Bug, Task | Issue type when available; `type:*` label fallback |
| Hierarchy | Nested sub-issues |
| Dependency | Native issue `blocked by` relationship |
| Workflow state | Project `Status` single-select field |
| Sprint | Project `Sprint` iteration field |
| Impact, Effort, Business Value, Enabler Value, Priority | Project number fields |
| Kanban | Board view grouped by `Status` |
| Current sprint | Board view filtered by `Sprint:@current` |
| Roadmap | Roadmap view over open, non-done issues |

## Priority model

The default base score is:

```text
Impact*2 + BusinessValue*2 + EnablerValue + (6-Effort)
```

For each prerequisite, the engine adds 25% of every direct dependent's final score. It evaluates the acyclic dependency graph from dependents back to prerequisites, then emits a topological order whose ready queue is sorted by descending final score and stable item ID.

Completed items score zero. Blocked or unrefined items are not executable. Sprint planning considers only Story, Bug, and Task by default, never schedules a dependent before its prerequisite, and never exceeds capacity.

## Safety boundary

The current release creates and updates managed issues, Project membership and fields, parent relationships, and missing dependencies. It does not delete issues, remove relationships, archive Project items, or automatically close completed issues. Those asymmetric operations are intentionally deferred because an incomplete local manifest must not destroy remote work.
