# Quickstart: from install to a first converged sync

This page takes a new user from nothing to a GitHub backlog the kit manages and
has verified. Each step writes nothing to GitHub until you confirm the exact
plan it showed you.

> **Status.** Written 2026-10-15 for S-R30-2. Followed end to end on a fresh
> organization repository between 2026-10-29 and 2026-11-06, to a sync plan
> with no actions left. The friction that run found is fixed here; the
> evidence is in [validation.md](validation.md).

## Before you start

Check these first. Each one is a hard requirement, not a recommendation.

- **A repository owned by an organization or a personal account.** The kit
  manages a GitHub Project owned by the same account as the repository.
  Projects are free on every GitHub plan. When the owner has no native issue
  type with exactly the item's type name, the kit marks that item with a
  `type:*` label instead. This is decided per type: a personal account has no
  native types, so every item gets a label, while an organization that defines
  `Feature` but calls its story type `User Story` gets the native Feature type
  and a `type:story` label.
- **One repository per manifest.** A manifest models one repository and one
  Project. Relationships to issues in other repositories are
  withheld, not followed.
- **GitHub access with these permissions:**
  - repository **Issues**: read and write;
  - **Projects** on the owning account: read and write;
  - repository **Contents**: read and write, only if the kit will create a
    Project or link one to the repository.

  With a classic token or `gh`, that is the `repo` and `project` scopes. Add the
  missing scope with `gh auth refresh -s project`. Fine-grained tokens need the
  permissions above on both the repository and the owning account.
- **One transport.** Either an authenticated `gh` CLI session, or `GH_TOKEN` or
  `GITHUB_TOKEN` in the environment. The kit prefers `gh` and falls back to the
  token; pass `--backend gh` or `--backend api` to choose.
- **Python 3.11 or later.** The engine has no third-party dependencies.

## 1. Install

Install the plugin in your agent host straight from GitHub, as the
[README](../README.md#install) shows for Claude Code and Codex. The agent then
drives every step below in natural language, through the six `backlog-*` skills.

The commands below are what those skills run. You can run them yourself to see
each plan before your agent applies it. They are written as `abk`, which is
shorthand, not an installed command: type `python <kit>/scripts/backlog.py` in
its place, where `<kit>` is the plugin's install folder or your clone of this
repository. Each command is on one line, so it pastes the same into bash, zsh
and PowerShell.

## 2. Create the manifest and the Project

Run these, and every command after them, from the root of your repository's
clone: the kit reads and writes `.agentic-backlog/` in the current directory.
`--owner` is the organization or user that owns the repository, and
`--repository` is the repository's bare name, without the owner. `init-plan` finds the
Project linked to the repository or titled like it, or proposes
creating one. It reads GitHub and writes nothing.

```bash
abk init-plan --owner YOUR-ACCOUNT --repository YOUR-REPO --output .agentic-backlog/cache/bootstrap-plan.json
```

The console prints a short summary: the plan file, its `digest`, the action
count, and the Project it selected, or `null` when it will create one. Open the
plan file to read the actions themselves; a new Project shows as one
`project.create` action. Several matching Projects stop the plan; pass
`--project-number N` or `--project-title TITLE` to choose one.

Apply exactly that plan by passing its digest:

```bash
abk init-apply --plan .agentic-backlog/cache/bootstrap-plan.json --confirm DIGEST --scaffold-plan .agentic-backlog/cache/scaffold-plan.json
```

This writes `.agentic-backlog/manifest.json` and a scaffold plan for the
Project's fields (Status, Sprint, Impact, Effort, Business Value, Enabler
Value, Priority), its type labels, and its Backlog, Kanban, Current Sprint and
Roadmap views. Review it and apply it the same way:

```bash
abk scaffold-apply --plan .agentic-backlog/cache/scaffold-plan.json --confirm DIGEST --receipt .agentic-backlog/receipts/scaffold-apply.json
```

GitHub cannot configure a view while creating it, so a new Project takes a
second round: the scaffold plan says so with `"converges_in_one_apply": false`
and a `follow_up` note. After the apply, read the Project again, plan, and
apply until the plan has no actions:

```bash
abk scaffold-snapshot --output .agentic-backlog/cache/scaffold.json
abk scaffold-plan --snapshot .agentic-backlog/cache/scaffold.json --output .agentic-backlog/cache/scaffold-plan.json
abk scaffold-apply --plan .agentic-backlog/cache/scaffold-plan.json --confirm DIGEST --receipt .agentic-backlog/receipts/scaffold-apply-2.json
```

On the first run the second plan holds one `project.view.update` for each of
Backlog, Kanban and Current Sprint, and the third plan is empty.

Commit `.agentic-backlog/manifest.json`. It is the backlog's desired state.
Keep plans and receipts out of version control by adding these lines to your
`.gitignore` before your first commit; the kit does not write them for you:

```gitignore
.agentic-backlog/cache/
.agentic-backlog/receipts/
.agentic-backlog/*.lock
```

## 3. Put work in

Choose one route.

**Start fresh.** Describe the work to your agent, or add items yourself, one
JSON file per item. A parent goes in first: an item can only name a parent or a
dependency that is already in the manifest. Give an item an `id` when another
item will point at it; the engine assigns a stable ID when you omit one. Save
each block to the file named above it.

`.agentic-backlog/cache/feature.json`:

```json
{
  "id": "F-ACCOUNT",
  "title": "Account recovery",
  "type": "Feature",
  "description": "Users who lose access to their account can get back in.",
  "acceptance_criteria": ["A user can regain access without contacting support"],
  "impact": 4, "effort": 3, "business_value": 4, "enabler_value": 2,
  "status": "Ready",
  "maturity": "refined"
}
```

`.agentic-backlog/cache/email.json`:

```json
{
  "id": "S-EMAIL",
  "title": "Send transactional email",
  "type": "Story",
  "parent": "F-ACCOUNT",
  "description": "The app can send a templated email to a user.",
  "acceptance_criteria": ["A templated email reaches the user's inbox"],
  "impact": 3, "effort": 2, "business_value": 2, "enabler_value": 4,
  "status": "Ready",
  "maturity": "ready"
}
```

`.agentic-backlog/cache/reset.json`:

```json
{
  "title": "Users can reset their password",
  "type": "Story",
  "parent": "F-ACCOUNT",
  "depends_on": ["S-EMAIL"],
  "description": "A user who forgot their password can set a new one from an emailed link.",
  "acceptance_criteria": ["A reset link is emailed", "The link expires after one hour"],
  "impact": 5, "effort": 2, "business_value": 5, "enabler_value": 1,
  "status": "Ready",
  "maturity": "ready"
}
```

```bash
abk item-add --input .agentic-backlog/cache/feature.json
abk item-add --input .agentic-backlog/cache/email.json
abk item-add --input .agentic-backlog/cache/reset.json
abk validate
```

`parent` becomes a GitHub sub-issue link and `depends_on` a "blocked by" link
on the first sync. A parent must sit exactly one level above its child:
Initiative, then Epic, then Feature, then Story or Bug, then Task. `validate`
rejects a skipped level, an unknown ID, and a dependency cycle before anything
reaches GitHub. The reset story scores higher than the email story, but
`abk next` will not offer it until the email story is done:
`abk next --explain 3` selects `S-EMAIL` and lists the reset story as passed
over, "waiting on S-EMAIL".

`item-add` prints the item's ID. The reset story has none in its file, so it
gets the next ID for its type, such as `STORY-0001`; `abk next` and the plans
name it by that ID from then on.

**Adopt issues the repository already has.** Preview first. It writes nothing:

```bash
abk import-plan --infer-relationships --output .agentic-backlog/cache/import-plan.json
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
abk sync-apply --plan .agentic-backlog/cache/sync-plan.json --confirm DIGEST --receipt .agentic-backlog/receipts/sync-apply.json
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
  re-running the old plan, and read the new plan before confirming it: an
  apply that closed the last open child of a parent makes the next plan
  propose `issue.close_parent` for that parent. Confirm that only if the
  parent is really finished; otherwise give it an open child first.

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
