---
name: backlog-init
description: Initialize or repair an Agentic Backlog Kit manifest and scaffold its GitHub Project fields, labels, Kanban, sprint, backlog, and roadmap views. Use for first-time setup or when required GitHub backlog structure is missing; do not use for adding ordinary backlog items.
---

# Initialize a backlog

Use GitHub Issues and the configured organization Project as the operational system of record. The tracked manifest is compact desired configuration, not a second live board.

1. Locate the plugin root containing `.codex-plugin/plugin.json`; use `python <plugin-root>/scripts/backlog.py` for deterministic operations.
2. Discover the repository owner/name from the current Git remote when possible. A Project title or number is optional.
3. If `.agentic-backlog/manifest.json` is absent, run `init-plan`. Project selection is deterministic; stop on ambiguous matches. When no match exists, the plan must show `project.create` explicitly.
4. Present the bootstrap actions and digest. Run `init-apply` only after the user accepts that exact digest. It refreshes GitHub, aborts before writes on drift, journals completed actions, captures the selected or created Project number in the new manifest, and emits a fresh scaffold plan from observed Project state. Never overwrite a manifest without an explicit request.
5. Present the scaffold action count, field/view/label summary, any view-configuration conflict, and the digest. Planning remains the default. A same-name view is matching only when its complete managed configuration matches, not merely its name and layout.
6. Apply only after the user explicitly accepts that exact scaffold digest. Pass it to `scaffold-apply`, which refreshes GitHub and aborts before writes if the manifest, scaffold state, or action preconditions changed. When using GitHub MCP, perform the equivalent fresh-state check.
7. The launcher journals every completed bootstrap or scaffold action. After success or interruption, refresh and re-plan. Success means zero remaining actions, including zero view updates; otherwise report and separately confirm the residual plan without replaying the interrupted plan. Never delete and recreate a same-name view to bypass an unsupported update.
8. After the Sprint field exists, resolve `@current` or `@next` from a fresh full iteration snapshot. If a safe contiguous extension is required, use the separately reviewed `iteration-plan` and `iteration-apply` workflow; do not assign backlog items until its post-apply identity verification succeeds.

For field mappings, permissions, and commands, read [references/scaffold.md](references/scaffold.md).

Report the manifest path, GitHub Project identity, applied changes, verification result, and any permission or issue-type fallbacks.
