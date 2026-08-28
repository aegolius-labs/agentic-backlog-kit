---
name: backlog-sprint-plan
description: Build and optionally commit a capacity-bounded, dependency-safe sprint from an Agentic Backlog Kit manifest. Use for sprint selection and iteration assignment; do not use for general backlog ranking alone.
---

# Plan a sprint

1. Locate the plugin root and validate the manifest.
2. Refresh a Project scaffold snapshot whenever a sprint target is supplied. Accept an exact title, `@current`, or `@next`; never resolve those from remembered dates or board state.
3. Use the requested capacity, or the manifest default when none is supplied. Run `python <plugin-root>/scripts/backlog.py sprint-plan --capacity N --sprint TARGET --snapshot .agentic-backlog/cache/scaffold.json [--as-of YYYY-MM-DD]`.
4. Present the resolved title and GitHub iteration ID, selected items in returned order, committed/remaining effort, and only the most material skipped reasons. Do not manually add an item the engine excluded.
5. `ready_to_commit: false` means the target needs a reviewed lifecycle update. Save an `iteration-plan`, present its digest and full preserved schedule, and run `iteration-apply` only after the user accepts that digest. The command refreshes before mutation, journals the action, refreshes again, and verifies that existing IDs/configuration were preserved. Then refresh and rerun sprint planning.
6. Planning alone is read-only. If the user asks to commit, proceed only when `ready_to_commit: true`; patch each selected item with the resolved iteration title (never an alias) and `status: Planned`, validate, then invoke the GitHub sync workflow.
7. If standard Project views are missing, produce a scaffold plan before synchronization. Do not create the Kanban or sprint board ad hoc.

Read [references/sprint-contract.md](references/sprint-contract.md) for eligibility and commitment rules.

After a GitHub commit, refresh and re-plan to verify the current-sprint board and iteration assignments. Stop if the target is completed, ambiguous, overlapping, stale/gapped, missing metadata, or changed identity.
