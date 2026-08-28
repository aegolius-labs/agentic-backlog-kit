# GitHub reconciliation contract

Only issues containing `<!-- agentic-backlog-kit:id=ITEM_ID;schema=1 -->` are managed. Unmarked issues and Project items are ignored.

Mapping:

- Item type: native organization issue type when available, otherwise `type:*` label.
- Parent: native sub-issue relationship.
- `depends_on`: native `blocked by` relationship.
- Status, Sprint, dimensions, and computed Priority: GitHub Project fields.

Executor order:

1. GitHub MCP when all required operations and identities are available.
2. `gh api` through an authenticated GitHub CLI session.
3. Direct REST/GraphQL API with `GH_TOKEN` or `GITHUB_TOKEN`.

Commands:

```text
python <plugin-root>/scripts/backlog.py snapshot --output .agentic-backlog/cache/remote.json
python <plugin-root>/scripts/backlog.py sync-plan --snapshot .agentic-backlog/cache/remote.json --output .agentic-backlog/cache/sync-plan.json
python <plugin-root>/scripts/backlog.py sync-apply --snapshot .agentic-backlog/cache/remote.json --plan .agentic-backlog/cache/sync-plan.json --confirm DIGEST --receipt .agentic-backlog/receipts/apply.json
```

The current reconciler is additive and update-only. It creates or updates managed issues, adds them to the Project, sets fields, adds parents, and adds missing dependencies. It does not infer deletion intent from a missing local item.
