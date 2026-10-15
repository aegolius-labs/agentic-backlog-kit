# Quickstart: from install to a first converged sync

This page takes a new user from nothing to a GitHub backlog the kit manages and
has verified. Each step writes nothing to GitHub until you confirm the exact
plan it showed you.

> **Status.** Written 2026-10-15 for S-R30-2. It has not yet been followed end
> to end on a fresh fixture repository. That run, and its evidence in
> [validation.md](validation.md), is still owed before S-R30-2 is done.

## Before you start

Check these first. Each one is a hard requirement, not a recommendation.

- **An organization account.** The kit manages an *organization-owned* GitHub
  Project. Every Project query it sends is `organization(login: ...)`, so a
  Project owned by a personal account cannot be used. The repository itself may
  belong to the organization or be linked to its Project.
- **One repository per manifest.** A manifest models one repository and one
  organization Project. Relationships to issues in other repositories are
  withheld, not followed.
- **GitHub access with these permissions:**
  - repository **Issues**: read and write;
  - organization **Projects**: read and write;
  - repository **Contents**: read and write, only if the kit will create a
    Project or link one to the repository.

  With a classic token or `gh`, that is the `repo` and `project` scopes. Add the
  missing scope with `gh auth refresh -s project`. Fine-grained tokens need the
  permissions above on both the repository and the organization.
- **One transport.** Either an authenticated `gh` CLI session, or `GH_TOKEN` or
  `GITHUB_TOKEN` in the environment. The kit prefers `gh` and falls back to the
  token; pass `--backend gh` or `--backend api` to choose.
- **Python 3.11 or later.** The engine has no third-party dependencies.

## 1. Install

Install the plugin in your agent host straight from GitHub, as the
[README](../README.md#install) shows for Claude Code and Codex. The agent then
drives every step below in natural language, through the six `backlog-*` skills.

The commands below are what those skills run. You can run them yourself to see
each plan before your agent applies it. They are written as `abk`. Inside an
installed plugin the same engine is `python <plugin-root>/scripts/backlog.py`;
from a clone it is `python scripts/backlog.py`.

## 2. Create the manifest and the Project

Run these from the root of your repository. `init-plan` finds the
organization Project linked to the repository or titled like it, or proposes
creating one. It reads GitHub and writes nothing.

```bash
abk init-plan --owner YOUR-ORG --repository YOUR-REPO \
  --output .agentic-backlog/cache/bootstrap-plan.json
```

Read the plan. It names the Project it selected, or shows a `project.create`
action, and ends with a `digest`. Several matching Projects stop the plan; pass
`--project-number N` or `--project-title TITLE` to choose one.

Apply exactly that plan by passing its digest:

```bash
abk init-apply --plan .agentic-backlog/cache/bootstrap-plan.json \
  --confirm DIGEST \
  --scaffold-plan .agentic-backlog/cache/scaffold-plan.json
```

This writes `.agentic-backlog/manifest.json` and a scaffold plan for the
Project's fields (Status, Sprint, Impact, Effort, Business Value, Enabler
Value, Priority), its type labels, and its Backlog, Kanban, Current Sprint and
Roadmap views. Review it and apply it the same way:

```bash
abk scaffold-apply --plan .agentic-backlog/cache/scaffold-plan.json \
  --confirm DIGEST \
  --receipt .agentic-backlog/receipts/scaffold-apply.json
```

Commit `.agentic-backlog/manifest.json`. It is the backlog's desired state.
Keep `.agentic-backlog/cache/` and `.agentic-backlog/receipts/` out of version
control.

## 3. Put work in

Choose one route.

**Start fresh.** Describe the work to your agent, or add one item yourself. The
engine assigns a stable ID when you omit one:

```json
{
  "title": "Users can reset their password",
  "type": "Story",
  "description": "A user who forgot their password can set a new one from an emailed link.",
  "acceptance_criteria": ["A reset link is emailed", "The link expires after one hour"],
  "impact": 4,
  "effort": 2,
  "business_value": 4,
  "enabler_value": 1,
  "status": "Ready",
  "maturity": "ready"
}
```

```bash
abk item-add --input .agentic-backlog/cache/item.json
abk validate
```

**Adopt issues the repository already has.** Preview first. It writes nothing:

```bash
abk import-plan --infer-relationships \
  --output .agentic-backlog/cache/import-plan.json
abk import-apply --plan .agentic-backlog/cache/import-plan.json --confirm DIGEST
```

Keep `--infer-relationships`. Without it, adopted items claim no parent or
dependency, and the next sync proposes removing the links GitHub already holds
between them. Adopted items start unrefined, so score them with your agent
before trusting the ranking.

## 4. Read a sync plan

```bash
abk sync-plan --output .agentic-backlog/cache/sync-plan.json
```

The command reads GitHub fresh and prints a short summary. Open the plan file
and check these fields before you confirm anything:

- **`actions`**, each with a `kind` and an `item_id`. On a first sync expect
  `issue.create`, `project.add_item`, and then the parent and dependency links.
  Kinds that remove or close something are the ones to read closely:
  - `issue.remove_parent` and `issue.remove_dependency` remove a link the
    manifest no longer declares, and carry a `restore` record that puts it back;
  - `issue.close_parent` closes a parent whose children are all closed.
- **`digest`**, a hash of the actions, the manifest, the GitHub state it read,
  and each action's preconditions. Confirming it approves exactly this plan
  and nothing else.
- **`held_remote_edits`**: titles or bodies someone edited on GitHub since the
  kit last wrote them. They are held, not overwritten. Accept the edit into the
  manifest, or pass `--overwrite-remote-edit ITEM_ID` to restore the manifest's
  version.
- **`priority_only`**: `true` when the plan only refreshes Priority scores.
  Such a plan is pre-authorized and may be applied without `--confirm`.

## 5. Apply, and verify convergence

```bash
abk sync-apply --plan .agentic-backlog/cache/sync-plan.json \
  --confirm DIGEST \
  --receipt .agentic-backlog/receipts/sync-apply.json
```

`sync-apply` reads GitHub again and rebuilds the plan before its first write.
If anything changed since you reviewed it, the digest no longer matches and it
stops without writing; plan again and review the new one. It records every
completed action in the receipt as it goes. Then it reads GitHub once more and
re-plans:

- `"verification": {"status": "converged"}` means GitHub now matches the
  manifest. `lag_observed: true` only means GitHub's reads took a few seconds to
  catch up.
- `drift` exits non-zero and lists the residual actions. Plan again rather than
  re-running the old plan.

A first sync is converged when a fresh `abk sync-plan` reports `"actions": 0`.

## What next

- `abk next --explain 5` names the next executable item and why it passed over
  the higher-ranked ones.
- `abk sprint-plan --capacity N --sprint @next --snapshot ...` packs a sprint.
  See the README.
- When a pull request completes a kit-managed issue, put `Closes #N` in its
  body. GitHub closes the issue on merge, and a Project with its built-in
  "Item closed" workflow enabled marks it Done.
  Never close a parent that way unless the pull request completes the parent's
  own acceptance criteria.
