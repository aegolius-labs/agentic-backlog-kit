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
5. Before apply, require explicit user acceptance of the exact plan. Refresh the snapshot and rebuild the plan; if the digest changes, present the new plan instead of applying the old one.
6. Apply the confirmed plan once, in order, using `sync-apply --confirm DIGEST` or equivalent GitHub MCP calls. Stop on the first failure and report the last confirmed action; do not guess or run unbounded retries.
7. Refresh and re-plan. Zero actions means verified convergence. Persist a receipt under `.agentic-backlog/receipts/` when using the launcher.

Read [references/github-mapping.md](references/github-mapping.md) for the remote mapping, executor choices, and non-destructive boundary.

Never delete issues, archive Project items, remove relationships, or close completed issues. This release intentionally treats those operations as out of scope.
