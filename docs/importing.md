# Adopting an existing backlog (R11)

Before this, the kit managed only issues it had created. An issue becomes
managed by carrying a marker in its body, and nothing put that marker on an
issue that already existed — so the kit was usable only on a repository that
started empty. For a product whose value is managing an existing GitHub
backlog, that was the gate on anyone adopting it.

## The shape of adoption

```bash
abk import-plan --output .agentic-backlog/import.json     # reads, writes nothing
abk import-apply --plan .agentic-backlog/import.json --confirm <digest>
```

`import-plan` lists the issues the kit does not manage, proposes a backlog item
for each, and says why every issue it did *not* propose was left out. It
performs no writes at all.

`import-apply` adopts exactly the issues in the reviewed plan: it adds the
marker to each issue's body and records the item in the manifest. Ordinary
synchronization then takes over.

## What adoption does and does not touch

| Adoption writes | Adoption leaves alone |
| --- | --- |
| The issue body, with the marker prepended | Title, labels, issue type, assignees |
| The local manifest | Comments, Project membership, milestones |
| | Every issue not in the plan |

The marker is **prepended**; nothing already in the body is removed. The
issue's existing body also becomes the item's `description`, so the content
survives when synchronization later renders the managed body.

## Proposed mapping

| Field | Source |
| --- | --- |
| `id` | `GH-<issue number>` — already unique and permanent in the repository |
| `title` | The issue title |
| `description` | The existing body, or the title when the body is empty |
| `type` | The native issue type or `type:` label, mapped into the manifest's vocabulary |
| `status` | `Done` for a closed issue; otherwise `Inbox` |
| `maturity` | `idea` — an adopted issue has not been refined by this backlog |
| scores | Neutral (3), enabler value 0 |
| `parent`, `depends_on` | Empty |

An organization defines its own issue types. `User Story` and `Tech Story` map
to `Story`, `Defect` to `Bug`, `Chore` to `Task`; anything the manifest's
hierarchy does not define adopts as `Task` rather than inventing a level.

Hierarchy and dependencies are **not** inferred yet. GitHub records sub-issue
links and `blocked_by` relationships, and reading them costs an extra request
per issue, which the first cut left out.

## Choosing what to adopt

```bash
abk import-plan --include 41 --include 42     # only these issues
abk import-plan --limit 20                    # the first twenty
```

Everything else is reported in `skipped` with its reason, so a partial adoption
never silently loses track of the rest.

## Duplicates

Two checks, with different severities.

**A colliding id is refused outright.** If the manifest already claims `GH-63`,
the plan fails rather than forking the item.

**A colliding title is withheld and reported.** An issue whose title matches a
managed item is very often the same work filed twice, so it is skipped with a
reason rather than adopted silently. Adopt it anyway with
`--allow-duplicate-titles`.

## Idempotence

Adoption marks the issue, and a marked issue is no longer unmanaged, so a
second `import-plan` proposes nothing. Re-running is safe.

## When adoption is interrupted

Adoption marks GitHub before the manifest records the item. If the manifest
write fails in between, the issue is stranded: import skips it because it is
already marked, and synchronization ignores it because no item claims it.

`import-plan` reports these as `orphans`, and repair is local only:

```bash
abk import-reconcile
```

This records the stranded markers in the manifest under the ids GitHub is
already using. It touches nothing on GitHub, because GitHub is already correct.

This is not hypothetical: the first live adoption hit exactly this, and the
recovery path exists because of it.

## After adopting

An adopted item enters the backlog unrefined by design — neutral scores,
`idea` maturity, no hierarchy. That is honest rather than helpful: the kit has
no basis for scoring work somebody else filed. Refine with `item-update`, then
synchronize.

The first synchronization after adoption will render the managed body template
around the preserved content. Pass `--preserve-body` if you would rather leave
the issue's formatting exactly as it is.

## Known limits

- Parent and dependency relationships are not inferred.
- Scores and maturity are neutral defaults, not inferred from labels or
  milestones.
- Adoption reads every issue in the repository; there is no incremental mode
  for a very large repository yet.
- An issue whose marker was hand-edited to a malformed id is treated as
  unmanaged and would adopt a second time under a new id.
