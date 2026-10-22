# GitHub reconciliation contract

Only issues containing `<!-- agentic-backlog-kit:id=ITEM_ID;schema=1 -->` are managed. Unmarked issues and Project items are ignored.

An item with a `guid` carries it in the same marker: `<!-- agentic-backlog-kit:id=ITEM_ID;schema=1;guid=GUID -->`. Items without one keep the plain marker, so existing issues are never rewritten for it. With `--preserve-body`, only the marker is corrected when its GUID differs; the rest of the body is left alone. A kit older than schema 2 that rewrites a body drops the key, and the next plan from a current kit restores it.

Every body the kit writes also carries a second, separate hidden comment at the end: `<!-- agentic-backlog-kit:written=v1;title=HEX;body=HEX -->`, one digest per field the kit can vouch for (a preserved body never gets one). `sync-plan` compares each digest against the remote's current title/body independently and, when one no longer matches, holds that field's update instead of planning it (the other field is unaffected) - see [operational-authority.md](../../../docs/operational-authority.md#edits-made-on-github). A missing or stale digest on a field that already matches the manifest gets a comment-only update installing a fresh one, so the first sync after upgrading proposes one for every such issue.

Mapping:

- Item type: native organization issue type when available, otherwise `type:*` label (always the label on a personal account).
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

The one exception to digest confirmation is a plan made solely of Priority field
updates, which the plan reports as `priority_only: true`. `sync-apply` accepts it
without `--confirm`. Every other check still applies: it refreshes GitHub, rebuilds
the plan, aborts if the digest moved, verifies after apply, and records
`authorization: "priority-only"` in the receipt. A `--confirm` that is given must
still match.

The reconciler creates or updates managed issues, adds them to the Project, sets fields, adds parents, and adds missing dependencies. It does not infer deletion intent from a missing local item.

It removes a relationship only when the manifest no longer declares it and both ends are manifest items: `issue.remove_parent` when an item that has a GitHub parent now declares none (a changed parent is replaced by `issue.set_parent`), and `issue.remove_dependency` for a `blocked by` link the item no longer lists. Each payload carries `restore`: the action kind, item ID, payload, and issue numbers that recreate the link. The receipt records it, so a removal can be undone with an ordinary plan. Removals run before additions, so reversing a dependency never asks GitHub to hold both directions. A link to an issue outside the manifest, managed or not, is never removed, and no removal closes or deletes an issue.

One closure is proposed, from evidence: `issue.close_parent` for an open parent whose manifest children are all closed on GitHub. It closes the parent with `state_reason: completed` and sets Status to the first done status when the Project does not already show it. The precondition records each child's number and closed state, so a child reopened after review changes the digest and apply aborts before its first write. A parent with no children, an open child, or a child not yet on GitHub is never proposed, and an issue the manifest no longer lists is never closed.
