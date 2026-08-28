---
name: backlog-init
description: Initialize or repair an Agentic Backlog Kit manifest and scaffold its GitHub Project fields, labels, Kanban, sprint, backlog, and roadmap views. Use for first-time setup or when required GitHub backlog structure is missing; do not use for adding ordinary backlog items.
---

# Initialize a backlog

Use GitHub Issues and the configured organization Project as the operational system of record. The tracked manifest is compact desired configuration, not a second live board.

1. Locate the plugin root containing `.codex-plugin/plugin.json`; use `python <plugin-root>/scripts/backlog.py` for deterministic operations.
2. Discover the repository owner/name from the current Git remote when possible. Ask only for values that cannot be discovered, including the organization Project number.
3. If `.agentic-backlog/manifest.json` is absent, run `init`. Never overwrite an existing manifest without an explicit request.
4. Run `validate`, then inspect GitHub with `scaffold-snapshot` and create a `scaffold-plan`.
5. Present the action count, field/view/label summary, and plan digest. Planning is the default; do not mutate GitHub yet.
6. Apply only after the user explicitly accepts that exact plan. Pass the exact digest to `scaffold-apply`, or execute the same actions through GitHub MCP if it exposes equivalent operations.
7. Refresh the scaffold snapshot and re-plan. Success means zero remaining actions; otherwise report the residual actions without silently retrying.

For field mappings, permissions, and commands, read [references/scaffold.md](references/scaffold.md).

Report the manifest path, GitHub Project identity, applied changes, verification result, and any permission or issue-type fallbacks.
