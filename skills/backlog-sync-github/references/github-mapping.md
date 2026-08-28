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
python <plugin-root>/scripts/backlog.py sync-apply --plan .agentic-backlog/cache/sync-plan.json --confirm DIGEST --receipt .agentic-backlog/receipts/apply.json
```

Sprint values must be resolved exact titles from a fresh Project iteration snapshot. Alias resolution and lifecycle extension belong to `iteration-plan`/`iteration-apply`; item-field assignment rejects aliases, completed iterations, duplicate titles, and missing refreshed IDs. A successful lifecycle apply is not sufficient by itself: refresh verification must prove existing IDs/configuration were unchanged and the target now has a GitHub ID before synchronization continues.

The saved snapshot is a planning input only. Apply refreshes GitHub and checks
that the rebuilt plan, including state fingerprints and action preconditions,
has the confirmed digest before performing its first mutation. Its receipt is
atomically rewritten after every completed action. After interruption, refresh
and confirm a newly generated remaining plan instead of replaying the old one.

The current reconciler is additive and update-only. It creates or updates managed issues, adds them to the Project, sets fields, adds parents, and adds missing dependencies. It does not infer deletion intent from a missing local item.
