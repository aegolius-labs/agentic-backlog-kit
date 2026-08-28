# Sprint contract

Default sprint-eligible types are Story, Bug, and Task. Initiative, Epic, and Feature remain tracking layers and do not consume sprint capacity.

An item is selectable when:

- maturity is `ready`;
- status is neither Done nor Blocked;
- every dependency is already Done or selected earlier in the same plan;
- its Effort fits remaining capacity.

The algorithm walks the dependency-valid priority order once. A prerequisite that cannot fit is skipped, and its dependent remains ineligible. This is deliberately deterministic rather than an optimizer that changes choices between runs.

Iteration target resolution uses a fresh normalized Project field snapshot:

- an exact title must identify one active iteration;
- `@current` means the single active interval containing the supplied/current date;
- `@next` means the earliest future active interval;
- completed titles and ambiguous, overlapping, stale/gapped, or incomplete schedules fail closed.

When the required current/next interval is absent, the engine can extend only a contiguous schedule with a matching duration and an unambiguous numeric-suffix title. A rollover with no current entry is safe only at the exact prior-iteration boundary; it creates deterministic current and next definitions. Any lifecycle change uses a separate digest-confirmed `iteration-plan`/`iteration-apply` flow.

GitHub's current `ProjectV2Iteration` input accepts title, start date, and duration but not an existing iteration ID or completion flag. Consequently, the update repeats every observed active definition unchanged, binds active and completed IDs/configuration in its precondition, and requires a post-apply refresh to prove that GitHub preserved them and assigned an ID to the new target. Never assign items before this verification succeeds.

Commands:

```text
python <plugin-root>/scripts/backlog.py scaffold-snapshot --output .agentic-backlog/cache/scaffold.json
python <plugin-root>/scripts/backlog.py iteration-plan --snapshot .agentic-backlog/cache/scaffold.json --target @next --as-of YYYY-MM-DD --output .agentic-backlog/cache/iteration-plan.json
python <plugin-root>/scripts/backlog.py iteration-apply --plan .agentic-backlog/cache/iteration-plan.json --confirm DIGEST --receipt .agentic-backlog/receipts/iteration-apply.json
python <plugin-root>/scripts/backlog.py sprint-plan --snapshot .agentic-backlog/cache/scaffold.json --sprint @next --as-of YYYY-MM-DD --capacity N
```

Committing a ready plan means updating only selected items with the resolved exact GitHub iteration title and `status: Planned`, validating the manifest, then using a reviewed sync plan. Sprint planning itself never mutates GitHub.

API contract: [GitHub Projects GraphQL reference](https://docs.github.com/en/graphql/reference/projects).
