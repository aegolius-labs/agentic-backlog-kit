---
name: backlog-sync-github
description: Reconcile managed Agentic Backlog Kit items with GitHub Issues and an organization Project through a safe plan, digest confirmation, apply, and verify workflow. Use for GitHub synchronization; do not use for unmanaged issue triage or destructive cleanup.
---

# Synchronize with GitHub

Use GitHub MCP when it exposes the exact operations in the plan. Otherwise use the plugin launcher, which prefers authenticated GitHub CLI and falls back to direct API access.

1. Locate the plugin root and validate the local manifest.
2. Refresh a remote snapshot. Never plan from remembered or conversational GitHub state.
3. Run `sync-plan` and present the action count by kind, affected stable IDs, and digest. Planning is the default.
4. If required Project fields or views are missing, stop and produce a scaffold plan first.
5. Before assigning Sprint, require an exact active iteration title and ID from a refreshed sprint/iteration plan. Never send `@current` or `@next` to the item-field mutation, and reject completed or ambiguous titles. If the lifecycle plan has an action, apply and verify it separately before rebuilding sync.
6. Before apply, require explicit user acceptance of the exact plan. The plan digest binds manifest and snapshot fingerprints plus action preconditions. `sync-apply` refreshes GitHub and rebuilds the plan itself; if the digest changes, it aborts before writes and the new plan must be presented and confirmed.
7. Apply the confirmed plan once, in order, using `sync-apply --confirm DIGEST` or equivalent GitHub MCP calls. The launcher journals each completed action. Stop on the first failure and report the receipt's completed prefix and failed action; do not guess or run unbounded retries.
8. After success, `sync-apply` verifies itself: it re-reads GitHub and re-plans. Residuals that ask again for values it just wrote are treated as GitHub's read-after-write lag and re-read for up to `--verify-window` seconds (default 60); a residual it did not write, or lag that outlasts the window, is drift. The receipt's `verification` records `status` (`converged` or `drift`), `lag_observed`, `reads`, and `convergence_seconds`, and the command exits non-zero on drift. After drift or interruption, refresh and re-plan. Zero actions means verified convergence. A remaining plan needs its own digest confirmation; never replay an interrupted plan blindly. Persist the receipt under `.agentic-backlog/receipts/` when using the launcher.

Read [references/github-mapping.md](references/github-mapping.md) for the remote mapping, executor choices, and non-destructive boundary.

Never delete issues, archive Project items, remove relationships, or close completed issues. This release intentionally treats those operations as out of scope.

If the plan reports `held_remote_edits`, a human changed that issue's title or body on GitHub since the kit's last write. Present each held item and its `hint` to the user; never pass `--overwrite-remote-edit` on your own judgment. Only apply it after the user explicitly says to restore the manifest's version over the GitHub edit.
