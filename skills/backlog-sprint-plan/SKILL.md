---
name: backlog-sprint-plan
description: Build and optionally commit a capacity-bounded, dependency-safe sprint from an Agentic Backlog Kit manifest. Use for sprint selection and iteration assignment; do not use for general backlog ranking alone.
---

# Plan a sprint

1. Locate the plugin root and validate the manifest.
2. Use the requested capacity, or the manifest default when none is supplied. Use an existing GitHub iteration title when the sprint will be committed.
3. Run `python <plugin-root>/scripts/backlog.py sprint-plan --capacity N --sprint TITLE`.
4. Present selected items in returned order, committed/remaining effort, and only the most material skipped reasons. Do not manually add an item the engine excluded.
5. Planning alone is read-only. If the user asks to commit, patch each selected item with the iteration title and `status: Planned`, validate, then invoke the GitHub sync workflow.
6. If standard Project views are missing, produce a scaffold plan before synchronization. Do not create the Kanban or sprint board ad hoc.

Read [references/sprint-contract.md](references/sprint-contract.md) for eligibility and commitment rules.

After a GitHub commit, refresh and re-plan to verify the current-sprint board and iteration assignments.
