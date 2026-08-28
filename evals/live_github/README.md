# Disposable live GitHub evaluation

This package is the Wave C runbook for proving the Agentic Backlog Kit against
real GitHub Issues and organization Projects. It is intentionally offline and
non-mutating: `scripts/live_github_eval.py` only prepares local fixtures,
materializes a manifest after a Project number is known, renders the semantic
plan, and verifies captured evidence. It has no GitHub transport or execution
command.

Run the complete suite once for each backend. Each run has a native-issue-type
variant and a label-fallback variant, giving this matrix:

| Backend | Native variant | Label variant | Write mechanism |
| --- | --- | --- | --- |
| GitHub CLI | required | required | `abk --backend gh` plus reviewed `gh` setup/cleanup commands |
| Direct API | required | required | `abk --backend api` plus reviewed REST/GraphQL setup/cleanup requests |
| GitHub MCP | required | required | canonical local plans; equivalent MCP actions executed one at a time |

If an MCP server cannot read or configure complete Project views, iterations,
hierarchy, or dependencies, fail that backend's preflight. Do not silently mix
write backends inside a variant. Reading through MCP into canonical snapshot
files and using the local deterministic planner is expected.

## 1. Prepare offline

Choose a new run ID for every backend. A UTC timestamp plus a short operator
identifier is a practical seed. The names are deterministic for auditability,
and different seeds produce different repository and Project names.

```powershell
python scripts/live_github_eval.py prepare `
  --output .agentic-backlog/evals/<backend-run-id> `
  --owner <sandbox-organization> `
  --run-id <backend-run-id> `
  --backend <gh-api-or-mcp> `
  --iteration-start <YYYY-MM-DD>

python scripts/live_github_eval.py show `
  --suite .agentic-backlog/evals/<backend-run-id>/suite.json
```

`mutation_authorized` is always `false`. The printed execution digest identifies
the suite but does not authorize a GitHub write. Every mutation still requires
the exact digest of its freshly built core plan. Resource creation that is not
yet represented by an ABK core plan needs a separately reviewed action record
containing the exact owner, repository name, Project title, visibility, backend,
and expected result.

## 2. Preflight before any write

Capture `<variant>/evidence/preflight.json` for both `native` and `labels`.
It must contain `passed: true`, the selected `backend`,
`redactions_confirmed: true`, the authenticated login, organization login,
permission checks, and capability results. Never record credentials, tokens,
Authorization headers, cookies, or credential-helper output.

Verify all of the following:

1. The organization is an approved disposable evaluation target, not a
   production repository or Project.
2. Both generated repository names and Project titles are absent. Stop on a
   collision; generate a new run ID instead of adopting an existing resource.
3. The authenticated identity can create/delete repositories, create/delete and
   link organization Projects, manage fields/views/iterations, create issues and
   labels, and create hierarchy/dependency relationships.
4. Native issue types needed by the fixture exist for the native variant. The
   labels variant must be configured as `labels` even when native types exist.
5. API rate limits are sufficient for a full run plus verification refreshes.
6. The evidence directory contains no secret-bearing shell or HTTP diagnostics.

Backend-specific probes are recorded in `suite.json`. A failed probe ends the
variant before resource creation.

## 3. Bootstrap and bind the Project identity

Create only the uniquely named disposable repository. Record the reviewed
resource-create action and response in `commands.ndjson`. Then use `init-plan`
to discover or propose the uniquely titled organization Project. Save the plan
as `bootstrap/plan.json`, inspect its owner/repository/title/actions, and pass its
exact digest to `init-apply`. The apply receipt belongs at
`bootstrap/receipt.json`.

After the created Project number is returned, bind it locally:

```powershell
python scripts/live_github_eval.py materialize `
  --suite .agentic-backlog/evals/<backend-run-id>/suite.json `
  --variant <native-or-labels> `
  --project-number <created-project-number>
```

This writes an empty `evidence/manifest.json` for ingestion and a complete
`expected-manifest.json` oracle. It does not contact GitHub. Do not replace the
empty manifest with the oracle.

## 4. Scaffold, ingest, rank, and plan

1. Refresh a scaffold snapshot and save the reviewed plan at
   `scaffold/plan.json`. Apply only its exact digest and retain the journaled
   `scaffold/receipt.json`.
2. Ingest the checked-in files under `<variant>/ingestion-items/` in numeric
   order with `item-add`. Validate after every item. This exercises the ingestion
   boundary while preserving stable IDs, hierarchy, dependencies, scoring, and
   the deliberately unrefined `STORY-0002`. Save the resulting ordered IDs in
   `ingestion/result.json`.
3. Capture deterministic `prioritize` output in
   `prioritization/result.json` and `sprint-plan --sprint Sprint 1` output in
   `sprint/plan.json`. Do not hand-edit either ordering.
4. Exercise `@current`, `@next`, completed-target rejection, duplicate-title
   rejection, overlap rejection, incomplete-metadata rejection, safe schedule
   extension, server-identity refresh, and a zero-action second lifecycle plan.
   Record raw plans/receipts in the command log and the boolean outcomes required
   by `iterations/assertions.json`.

Refresh `scaffold/after.json` after the iteration exercise. It must include field
identity and iteration configuration plus complete view configuration—not just
view names and layouts. The oracle checks filter, visible-field order, horizontal
and vertical grouping, and sort order.

## 5. Synchronize, apply, and prove convergence

Capture `sync/plan.json` from a fresh managed snapshot. Inspect issue bodies,
stable ABK markers, native/fallback typing, Project fields, parents, dependencies,
and iteration values. Apply only the exact reviewed digest. Keep the journaled
`sync/receipt.json`, refresh into `sync/after.json`, and rebuild both plans:

- `scaffold/second-plan.json` must contain zero actions;
- `sync/second-plan.json` must contain zero actions;
- the iteration lifecycle second plan must contain zero actions.

For native mode, every managed issue must expose the fixture's issue type. For
labels mode, every issue must carry exactly the corresponding managed
`type:<lowercase>` fallback while unrelated labels remain untouched. Hierarchy,
dependencies, Status, Sprint, and all scoring fields must match the final
manifest.

Write `assertions.json` only after reviewing the captured state. Then run the
offline verifier:

```powershell
python scripts/live_github_eval.py verify `
  --suite .agentic-backlog/evals/<backend-run-id>/suite.json
```

The verifier fails on missing evidence, non-completed or mismatched receipts,
incomplete fields/views/iterations, divergent ranking or sprint selection,
typing/hierarchy/dependency drift, or non-empty second plans. Preserve the full
redacted evidence directory as the Wave C artifact.

## 6. Cleanup is a separate destructive operation

Do not clean up as part of a successful evaluation command. First preserve and
review evidence, verify the suite, and re-query GitHub to resolve the exact
repository owner/name and Project node ID. Compare both to `suite.json`; stop on
any mismatch.

The suite contains a `cleanup_confirmation` that is deliberately different from
the execution digest. Obtain separate human confirmation quoting that cleanup
digest and the exact two Project titles and repository names. Then, one variant
at a time:

1. Delete the disposable organization Project by its freshly resolved node ID.
2. Refresh and prove that Project is absent.
3. Delete the disposable repository by its literal `owner/name`—never by a
   wildcard, environment-derived path, or search result.
4. Refresh and prove that repository is absent.
5. Record redacted cleanup requests, responses, target identities, confirmation
   digest, and verifier evidence in a separate cleanup receipt.

GitHub deletion is not an Agentic Backlog Kit backlog mutation and is therefore
never added to the product's sync engine. If separate confirmation is unavailable
or any identity differs, leave the resources intact and report cleanup as
blocked.
