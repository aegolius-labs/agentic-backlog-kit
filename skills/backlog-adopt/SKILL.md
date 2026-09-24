---
name: backlog-adopt
description: Take an existing GitHub repository's issues under Agentic Backlog Kit management through a read-only preview, digest confirmation, and adoption apply, optionally proposing the sub-issue and dependency structure GitHub already records. Use when a repository already has issues that are not yet managed; do not use for creating new work, for ordinary reconciliation of already-managed items, or for destructive cleanup.
---

# Adopt an existing backlog

An issue is managed only when its body carries `<!-- agentic-backlog-kit:id=ITEM_ID;schema=1 -->`. Nothing else makes an issue managed, so a repository that already has issues is invisible to synchronization until it is adopted. Ingestion handles one structured item at a time; do not re-file an existing backlog by hand.

Keep model context bounded. The preview is a mapping, not a backlog to read aloud: report counts, the ids proposed, and what was withheld or skipped, not every item body.

1. Locate the plugin root and run `python <plugin-root>/scripts/backlog.py validate`. Adoption needs a manifest to adopt into; if there is none, use `$backlog-init` first.
2. Run `import-plan`. It reads and writes nothing. Present the proposed item count, the skipped issues with their reasons, and the digest.
3. Decide about relationships before previewing, because it changes the plan and its digest. Pass `--infer-relationships` to propose the sub-issue parent and `blocked by` dependencies GitHub already records. It is off by default because it changes the plan and costs one extra batched read per 50 unmanaged issues. Without it every item adopts with `parent: null` and `depends_on: []`, and because reconciliation is additive it will never remove the relationships GitHub still holds — the manifest simply disagrees with the repository, permanently.
4. Report every withheld relationship and why. A withheld relationship is not a failure: the manifest's hierarchy is a strict ladder and its dependency graph must stay acyclic, both narrower than what GitHub permits. Never retype an item or drop a dependency to force one through.
5. Narrow the adoption when the user wants a subset: `--include NUMBER` per issue, or `--limit N`. Everything else is reported under `skipped` with its reason. Do not silently adopt a whole repository the user asked to sample.
6. Before apply, require explicit acceptance of the exact plan. `import-apply --plan PLAN --confirm DIGEST` re-reads the repository, rebuilds the plan the same way it was previewed, and aborts before the first write if the digest changed. Present the new plan and reconfirm rather than forcing the old one.
7. Adoption prepends the marker to each issue body and records the item locally. It changes nothing else — not the title, labels, issue type, assignees, comments, Project membership, or milestones — and it never touches an issue outside the plan.
8. If `import-plan` reports `orphans`, an earlier adoption marked GitHub and failed before the manifest recorded it. Repair is local only: run `import-reconcile`, which records those markers under the ids GitHub already uses and writes nothing remote. Pass `--infer-relationships` there too, on the same terms and for the same reason as adoption — a recovered item that claims no structure while GitHub still holds one disagrees with its own repository permanently, because synchronization will never remove what GitHub has. Never adopt an orphan a second time; that forks the item.
9. After adopting, refresh and reconcile with `$backlog-sync-github`. Adopted items are unrefined by design — neutral scores, `idea` maturity — so refine with `$backlog-ingest` before treating any score as meaningful. The first synchronization renders the managed body template around the preserved content; pass `--preserve-body` to leave the issue's formatting exactly as written.

Read [references/adoption-contract.md](references/adoption-contract.md) for the proposed field mapping, the relationship rules, and the commands.

Never close, delete, or retype an issue to make it adoptable, and never invent a hierarchy level the manifest does not define.
