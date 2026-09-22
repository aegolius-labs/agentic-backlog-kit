# Adoption contract

An issue is unmanaged until its body carries `<!-- agentic-backlog-kit:id=ITEM_ID;schema=1 -->`. Adoption is the only thing that writes that marker onto an issue the kit did not create.

## Proposed mapping

| Field | Source |
| --- | --- |
| `id` | `GH-<issue number>` — already unique and permanent in the repository |
| `title` | The issue title |
| `description` | The existing body, or the title when the body is empty |
| `type` | The native issue type or `type:` label, mapped into the manifest's hierarchy |
| `status` | The first done status for a closed issue; otherwise `Inbox` |
| `maturity` | `idea` — an adopted issue has not been refined by this backlog |
| scores | Neutral (3), enabler value 0 |
| `parent`, `depends_on` | Empty, unless `--infer-relationships` is passed |

An organization defines its own issue types. `User Story` and `Tech Story` map to `Story`, `Defect` to `Bug`, `Chore` to `Task`; anything the hierarchy does not define adopts as `Task` rather than inventing a level.

## Relationships

`--infer-relationships` reads each unmanaged issue's sub-issue parent and `blocked by` set and proposes them. It costs two extra reads per unmanaged issue, which is why it is opt-in.

A relationship is proposed only when the manifest can express it. Everything else is reported under `withheld_relationships`, keyed by item:

| Observed | Outcome |
| --- | --- |
| Parent adopted in this same plan, one hierarchy level above | Proposed |
| Parent already a managed item, one level above | Proposed |
| Parent not exactly one level above the child | Withheld |
| Related issue neither managed nor part of this adoption | Withheld |
| Related issue marked but not recorded in the manifest | Withheld — reconcile first, then re-plan |
| Dependency that would close a cycle | Withheld — the earlier edge wins, deterministically by item id |

A repository whose issue types fall outside the hierarchy adopts as `Task` throughout, and `Task` cannot parent `Task`, so its whole structure reports as withheld. That is the strict ladder being honest, not a defect to work around.

The plan records which mode built it. `import-apply` re-reads the repository the same way and rebuilds with the same setting before comparing digests, so a plan whose mode was edited after review is refused rather than applied.

## Commands

```text
python <plugin-root>/scripts/backlog.py import-plan --infer-relationships --output .agentic-backlog/cache/import-plan.json
python <plugin-root>/scripts/backlog.py import-apply --plan .agentic-backlog/cache/import-plan.json --confirm DIGEST --receipt .agentic-backlog/receipts/import-apply.json
python <plugin-root>/scripts/backlog.py import-reconcile
```

`--include NUMBER` adopts only the given issues, repeated per issue. `--limit N` adopts the first N. `--allow-duplicate-titles` adopts an issue whose title already matches a managed item, which is withheld by default because it is usually the same work filed twice. A colliding item id is refused outright rather than forked.

## Boundary

Adoption writes the issue body marker and the local manifest. It does not change the title, labels, issue type, assignees, comments, Project membership, or milestones, and it touches no issue outside the plan.

Adoption marks GitHub before the manifest records the item, so an interruption can strand a marked issue that no item claims. `import-plan` reports those as `orphans`; `import-reconcile` records them locally under the ids GitHub already uses and writes nothing remote. Adopting a stranded issue again forks it.

Adoption is idempotent. A marked issue is no longer unmanaged, so a second `import-plan` proposes nothing.
