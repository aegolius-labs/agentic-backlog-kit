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

From an installed plugin this is the `$backlog-adopt` skill, whose
[adoption contract](../skills/backlog-adopt/references/adoption-contract.md)
carries the same rules in the form an agent reads.

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
| `parent`, `depends_on` | Empty, unless `--infer-relationships` is passed |

An organization defines its own issue types. `User Story` and `Tech Story` map
to `Story`, `Defect` to `Bug`, `Chore` to `Task`; anything the manifest's
hierarchy does not define adopts as `Task` rather than inventing a level.

## Inferring hierarchy and dependencies

GitHub already records sub-issue links and `blocked_by` relationships. Adoption
flattens them by default, and `--infer-relationships` proposes them instead:

```bash
abk import-plan --infer-relationships --output .agentic-backlog/import.json
```

It is opt-in because it changes the plan and its digest. It costs one extra
batched GraphQL read per 50 unmanaged issues, carrying each issue's parent and
dependencies, on top of the single listing adoption otherwise performs. Before
S-R28-1 it cost two REST reads per issue, which on a repository of any size was
the difference between one request and hundreds.

A relationship into another repository is withheld with its reason rather than
matched: one manifest models one repository, and an issue number means nothing
outside its own.

Flattening was not merely incomplete, it was a divergence: synchronization is
additive and never removes a parent or a dependency, so an adopted issue kept
its GitHub structure while the manifest said it had none, and nothing ever
reconciled the two. Inferring the structure is what makes the manifest agree
with the repository it adopted.

### What gets proposed, and what gets withheld

A relationship is proposed only when it can be expressed as this manifest's
own rules allow. Everything else is dropped and reported under
`withheld_relationships`, keyed by the item it belongs to:

| Observed | Outcome |
| --- | --- |
| Parent is adopted in this same plan, one hierarchy level above | Proposed |
| Parent is already a managed item, one level above | Proposed |
| Parent is not exactly one level above the child | Withheld — the hierarchy forbids it |
| Related issue is neither managed nor part of this adoption | Withheld — the id would not exist |
| Related issue carries a marker the manifest does not record | Withheld — run `import-reconcile` first, then re-plan |
| A dependency that would close a cycle | Withheld — the earlier edge wins, deterministically by item id |

Nothing is forced. A repository whose issue types do not match the manifest's
hierarchy adopts as `Task` throughout, and `Task` cannot parent `Task`, so its
structure is reported as withheld rather than invented. That is the honest
outcome, and it is the same strict-ladder constraint R24 is open about.

The plan records which mode built it. `import-apply` re-reads the repository
the same way and rebuilds the plan with the same setting before comparing
digests, so a plan whose mode was edited after review is refused rather than
applied.

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

Pass `--infer-relationships` here too. Recovery without it produces exactly the
divergence relationship inference exists to prevent: the item claims no parent
while GitHub still holds one, and additive synchronization will never reconcile
that. Recovery resolves against the ids it is about to write as well as the
manifest, because one stranded issue can be the parent of another.

This is not hypothetical: the first live adoption hit exactly this, and the
recovery path exists because of it.

## After adopting

An adopted item enters the backlog unrefined by design — neutral scores and
`idea` maturity, and no hierarchy unless it was inferred. That is honest rather
than helpful: the kit has no basis for scoring work somebody else filed. Refine with `item-update`, then
synchronize.

The first synchronization after adoption will render the managed body template
around the preserved content. Pass `--preserve-body` if you would rather leave
the issue's formatting exactly as it is.

## Known limits

- Relationship inference costs one extra batched read per 50 unmanaged issues and has
  no batched or GraphQL route yet.
- A withheld relationship is reported, not repaired. Retyping the items and
  re-planning is manual.
- Recovery repairs only the items it recovers. An already-managed item whose
  local intent disagrees with GitHub is left alone, and reconciling that
  direction is R10's scope, not adoption's.
- Scores and maturity are neutral defaults, not inferred from labels or
  milestones.
- Adoption reads every issue in the repository; there is no incremental mode
  for a very large repository yet.
- An issue whose marker was hand-edited to a malformed id is treated as
  unmanaged and would adopt a second time under a new id.
