# Agentic Backlog Kit Roadmap

Last updated: 2026-09-04

## Product goal

Create a Codex-first plugin that lets agents manage GitHub Issues and Projects through focused skills and deterministic, low-token local tooling.

## Architectural decisions

- GitHub Issues and Projects are the operational system of record.
- The tracked local manifest contains configuration, stable local IDs, hierarchy, scoring inputs, and desired GitHub metadata. It is not a second human-managed board.
- Generated remote snapshots, ID mappings, and apply receipts are disposable local state and must not be committed.
- Every external mutation follows `plan -> validate -> apply`; planning is the default.
- Backlog hierarchy defaults to `Initiative -> Epic -> Feature -> Story/Bug -> Task`.
- GitHub sub-issues represent hierarchy; native issue dependencies represent blocking relationships; Project fields represent planning metadata.
- Priority is computed locally from Impact, Effort, Dependencies, Enabler value, and Business Value. Dependency ordering is cycle-safe and deterministic.
- Native GitHub Projects access is a first-class transport invariant across a capability-complete Codex GitHub integration/GitHub MCP, authenticated GitHub CLI, and direct GraphQL/REST API. Skills select one complete route per apply, never silently mix write transports, and keep the local engine provider-neutral.
- The implementation uses test-first development for schemas, scoring, planning, reconciliation, and mutation safety.

## Milestones

### M0 - Discovery and boundaries

- [x] Confirm product scope and hierarchy with the owner.
- [x] Review current OpenAI plugin and skill architecture.
- [x] Inspect backlog-management concepts in `aio-agentic-sdlc`.
- [x] Verify current GitHub support for nested sub-issues, issue dependencies, Project fields, iterations, and programmatic board views.
- [x] Document the extraction boundary and attribution.

### M1 - Installable plugin foundation

- [x] Create and validate the `.codex-plugin/plugin.json` manifest.
- [x] Add focused skills for initialization, ingestion, prioritization, sprint planning, and GitHub sync.
- [x] Add concise UI metadata and GitHub tool dependency declarations.
- [x] Document installation and the Codex-first UX.

### M2 - Deterministic local engine

- [x] Define and validate the compact manifest schema.
- [x] Implement cycle detection, dependency-aware priority scoring, and stable tie-breaking.
- [x] Implement capacity-aware sprint selection.
- [x] Emit concise human and JSON results so agents do not need to read the full backlog.
- [x] Cover the core behavior with unit and adversarial tests.

### M3 - GitHub reconciliation

- [x] Discover GitHub repository, organization Project, fields, iterations, issues, hierarchy, and dependency state.
- [x] Produce an idempotent sync plan without mutation.
- [x] Validate hierarchy, cycles, plan integrity, and field compatibility before apply; surface permission failures without retry loops.
- [x] Bind apply to freshly verified local and remote state and journal partial execution (R01).
- [x] Apply creates and updates through GitHub CLI/API, stopping on first failure and writing receipts.
- [x] Support a capability-complete GitHub MCP as an interactive route and authenticated GitHub CLI/direct GraphQL API as peer native routes under the same plan/apply contract.

### M4 - Backlog and sprint scaffolding

- [x] Scaffold labels, issue types or fallback type labels, Project fields, and standard statuses.
- [x] Create backlog table, Kanban board, sprint board, and roadmap views.
- [x] Create or select iterations and assign a dependency-valid sprint slice.
- [x] Add example manifests and a safe demo workflow.
- [x] Create or discover the organization Project during first-run setup (R03).
- [x] Reconcile complete filters, grouping, sorting, and other view configuration (R04).
- [x] Manage current, next, completed, and rolling iterations (R05).

### M5 - Release readiness

- [x] Run plugin and skill validators.
- [x] Run the complete test suite on a hosted Linux runner and verify the same tagged checkout locally.
- [x] Add GitHub Actions for tests and package validation.
- [x] Build and inspect the Python package and add a tag-driven GitHub release workflow.
- [x] Select the noncommercial/paid-commercial licensing model and add release, support, security, and contribution documentation (R08).
- [x] Perform realistic dry-run and apply evaluations against disposable repositories and organization Projects (R02).
- [x] Evaluate the installed plugin and skill activation through Codex (R06).
- [x] Measure and enforce token-efficiency budgets (R09).
- [x] Publish the initial `0.1.0` release and document known limitations.

## Current checkpoint

Wave D completed on 2026-09-04. The canonical public repository is published at `aegolius-labs/agentic-backlog-kit`; hosted `ubuntu-latest` CI passed all 168 tests plus package and byte-budget checks on release commit `6a14b70`; `main` has strict `test` protection with administrator enforcement and force-push/deletion disabled; and `v0.1.0` is published with validated wheel and source-distribution assets. A clean clone of the public tag passes the full suite, CLI, benchmark, plugin, and five skill validators. The separately approved disposable-resource cleanup stopped safely on its first repository-deletion failure: Project #4 is deleted, its private repository remains, and the API Project #5/repository were untouched. Cleanup now requires a fresh identity-bound plan; it does not block the completed release. Wave E post-release product work is ready to begin.

## Work items, ranked

Complexity labels describe implementation and validation effort, not importance.

### Release-critical work

#### R01 - Bind apply operations to fresh local and remote state

- **Status:** Complete in Wave A
- **Importance:** Critical
- **Complexity:** Hard
- **Context:** Sync, scaffold, and bootstrap plans now bind normalized local/remote fingerprints and per-action preconditions. Apply refreshes GitHub, rebuilds the reviewed plan, and aborts before mutation on drift. Atomic receipts record each completed action and any failed action.
- **High-level approach:** Completed through shared execution receipts, plan-bound fingerprints, apply-time refresh/replanning, failure injection, and interruption tests. Recovery always starts from a new reviewed plan.
- **Done when:** Local or remote drift aborts before the first write; partial failure produces an auditable receipt; rerunning after interruption converges safely; concurrency and failure-injection tests pass.

#### R02 - Run live GitHub end-to-end evaluations

- **Status:** Complete in Wave C for every supported route; authenticated GitHub CLI and direct GraphQL/REST label-fallback workflows both converged end to end with zero-action second plans
- **Importance:** Critical
- **Complexity:** Hard
- **Context:** The live evaluation exercised approved disposable repositories and organization Projects through the complete initialization, scaffolding, ingestion, prioritization, sprint, and synchronization lifecycle. Both supported native GitHub transports converged with eight managed issues and exact hierarchy, dependency, iteration, view, and planning-field state. The native issue-type variants failed capability preflight because `Story` is unavailable, while the installed generic GitHub MCP lacks the Project surface; neither unsupported route performed writes.
- **High-level approach:** Completed with fresh-state-bound plans, exact digest confirmations, journaled applies, canonical post-apply snapshots, full state assertions, and zero-action replans. The direct API observation also records eventual Project-membership propagation: the immediate recheck retained eight residual additions, no unconfirmed replay occurred, and a later read-only refresh converged. Exact-target cleanup remains separately gated.
- **Done when:** Each supported executor completes the representative workflow, the second plan contains zero actions, failure cases are recorded, and the resulting GitHub state matches the manifest and view contracts.

#### R03 - Complete first-run Project creation and discovery

- **Status:** Complete in Wave A
- **Importance:** High
- **Complexity:** Hard
- **Context:** `init-plan` now discovers organization Projects by exact number/title or unique repository association, fails closed on ambiguity, and plans explicit creation when none exists. `init-apply` captures and persists Project identity, refreshes GitHub, and produces the separately reviewed scaffold plan.
- **High-level approach:** Completed with paginated Project/link discovery, current GraphQL create/link mutations, digest-confirmed apply, fresh-state validation, atomic action receipts, and simulated API tests.
- **Done when:** A user can start with only an organization and repository, explicitly select or create a Project, and reach an idempotent fully scaffolded state.

#### R04 - Reconcile complete Project view configuration

- **Status:** Complete in Wave B
- **Importance:** High
- **Complexity:** Medium
- **Context:** Scaffold snapshots now retain view node/number identity, layout, normalized filter, ordered visible fields, horizontal/vertical grouping, and ordered sorting with both GraphQL and REST field identities. A same-name view is never accepted from name/layout alone.
- **High-level approach:** Complete view state is compared semantically. Layout, filter, and applicable visible-field drift produce fresh-state-bound `project.view.update` actions. Grouping or sorting drift produces a precise fail-closed conflict because GitHub's current view-update input does not expose those settings; the kit never deletes/recreates a view to work around that boundary.
- **Done when:** Incorrect same-name views are detected, repair plans converge, and a second scaffold plan is empty only when the full view contract matches.

#### R05 - Manage the iteration lifecycle

- **Status:** Complete in Wave B and live-verified in Wave C; both GH and direct-API Sprint 1 fields are initialized with stable server identities and zero remaining lifecycle actions
- **Importance:** High
- **Complexity:** Medium
- **Context:** Full active/completed iteration definitions and identities are now canonical snapshot state. Sprint planning resolves exact titles, `@current`, and `@next` before commitment and rejects completed, duplicate, overlapping, stale/gapped, duration-mismatched, or otherwise ambiguous schedules.
- **High-level approach:** Safe missing-current/next cases produce a separately reviewed full-configuration update that preserves every observed active definition and extends only contiguous numeric-suffix schedules. Wave C additionally proved that GitHub may create an empty iteration field while ignoring its empty configuration; the canonical snapshot now retains that uninitialized state without inventing a start or identity, and a separate initialization plan binds the null-start/empty precondition. Apply is digest/fresh-state bound and journaled. Because GitHub's mutation input does not accept existing IDs or completion state, those remain preconditions and mandatory post-refresh invariants; item assignment stays blocked until the refreshed target ID is present.
- **Done when:** Sprint planning can select a valid current or next iteration, missing iterations are handled through a reviewed plan, and rollover/completed-iteration tests pass.

#### R06 - Evaluate the installed plugin and skill activation

- **Status:** Complete in Wave C with token-bounded representative real traces and complete deterministic corpus/verifier coverage
- **Importance:** High
- **Complexity:** Medium
- **Context:** The plugin was installed and enabled from the personal local marketplace, structurally validated, and exercised through real Codex conversations covering direct, indirect, follow-up, negative, boundary, and write-confirmation behavior. The durable two-turn trace proves fresh-task identity, exact-session reuse, result-ID continuity, zero workspace mutation, no external contact, redaction, and reported token use. The complete 17-case/two-mode corpus remains available to the deterministic verifier; the full real 34-pair matrix was intentionally not executed because representative traces already exposed the integration defects and the project prioritizes bounded token use.
- **High-level approach:** Keep real evaluation representative and bounded, while the deterministic harness enforces every corpus pair's evidence contract. Real traces fail closed on malformed/truncated output, incomplete turns, unproven references, unexpected filesystem changes, external contact, missing confirmation, or lost continuation identity. The installed generic GitHub MCP is recorded as capability-incomplete rather than pretending `mcp_available`; authenticated `gh` and direct GraphQL/REST remain the supported native Project routes.
- **Done when:** The intended skill activates consistently, unsupported requests do not activate it, bundled references resolve after installation, and authorization boundaries hold in end-to-end conversations.

#### R07 - Publish the repository, run Linux CI, and release `0.1.0`

- **Status:** Complete in Wave D; canonical repository, hosted Linux CI, branch protection, tag, release assets, and clean public-checkout verification all passed
- **Importance:** High
- **Complexity:** Medium
- **Context:** The public repository and `v0.1.0` release are live. Hosted Actions validated all 168 tests, CLI help, the package build/install, legal-artifact preflight, and token budgets on the exact release commit. Branch protection requires the successful `test` context and applies to administrators; release assets were downloaded, revalidated, installed, and smoke-tested.
- **High-level approach:** Completed through an exact identity- and commit-bound publication plan: create one public repository, push only the reviewed candidate, require green hosted CI, protect `main`, publish one annotated tag, verify the generated release and assets, then rerun the checks from a clean public tag clone.
- **Done when:** Windows and Linux checks are green from a clean checkout, branch protection is active, installation instructions work, and the tagged release contains documented artifacts and limitations.

#### R08 - Select a license and complete public-release documentation

- **Status:** Complete in Wave D; final licensing metadata, legal artifacts, support boundaries, and Wave C limitations are included in `v0.1.0`
- **Importance:** High
- **Complexity:** Easy
- **Context:** The kit is source-available under PolyForm Noncommercial 1.0.0, with a separate paid license required for any for-profit operational use. Individuals may use it for genuinely noncommercial open-source work; making a project public does not convert commercial use into noncommercial use.
- **High-level approach:** Completed with consistent license/package metadata, commercial terms guidance, `SECURITY.md`, `SUPPORT.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, and release documentation. Final known limitations will be refreshed from Wave C results before release.
- **Done when:** Repository and package metadata agree, users understand permissions and support boundaries, and the release checklist contains no unresolved legal or documentation placeholders.

#### R09 - Measure and enforce token-efficiency targets

- **Status:** Complete; the Wave C release-candidate rerun is deterministic and within every budget at 100, 1,000, and 10,000 items
- **Importance:** Medium
- **Complexity:** Medium
- **Context:** Deterministic 100-, 1,000-, and 10,000-item fixtures now measure compact and pretty JSON for `summary`, `show`, `next`, prioritization, sprint planning, snapshots, and cold sync plans. Byte budgets are enforced in CI, with tokenizer-free estimates reported for planning.
- **High-level approach:** Completed with a local benchmark harness, documented baselines, SHA-256 payload digests, fixed/linear byte envelopes, and bounded `sprint-plan --skipped-limit` projections for model-facing output.
- **Done when:** Token or byte budgets are documented, large-backlog benchmarks are repeatable, and CI detects material output-size regressions.

### Post-`0.1.0` product work

#### R10 - Add destructive and reverse reconciliation

- **Importance:** Medium
- **Complexity:** Hard
- **Context:** Synchronization is deliberately additive and update-only. It does not close deleted work, remove obsolete parents or dependencies, archive Project items, or reconcile remote-only changes back into local intent.
- **High-level approach:** Define authority and conflict policies for every managed field. Introduce explicit destructive action types with stronger confirmations, remote preconditions, soft-delete/archive defaults, recovery information, and comprehensive audit tests.
- **Done when:** Every removal or reverse-sync behavior has an explicit policy, preview, confirmation boundary, audit trail, and recovery path.

#### R11 - Import existing backlogs and support bulk ingestion

- **Importance:** Medium
- **Complexity:** Medium
- **Context:** Ingestion handles one structured item at a time and only marked GitHub issues are managed. Adopting an established repository would therefore require significant manual work.
- **High-level approach:** Add a read-only import preview for unmanaged issues, infer candidate types and relationships, detect duplicates, let users review mappings, assign stable ABK IDs, and apply adoption in deterministic batches.
- **Done when:** An existing repository can be imported without modifying unselected issues, duplicate mappings are rejected, and a second import is idempotent.

#### R12 - Support multi-repository portfolio planning

- **Importance:** Later
- **Complexity:** Hard
- **Context:** One manifest currently targets one repository and one organization Project. Cross-repository initiatives and dependencies are outside the current authority model.
- **High-level approach:** Separate portfolio items from repository-owned delivery items, introduce repository-qualified stable references, support cross-repository dependencies, and retain compact per-repository snapshots.
- **Done when:** Multiple repositories can participate in one portfolio Project without ID ambiguity or loading every repository backlog into model context.

#### R13 - Complete native transport parity and decide whether to build a dedicated MCP server

- **Status:** Decision gate opened by Wave C evidence; direct GraphQL works, installed generic GitHub MCP is incomplete for Projects
- **Importance:** High
- **Complexity:** Hard
- **Context:** The product requirement is native GitHub Projects interaction through the Codex GitHub integration/GitHub MCP when it exposes the complete surface, or through direct GraphQL/REST calls. Wave C proved the authenticated CLI and direct API routes can discover and create Projects, while the installed generic GitHub MCP lacks repository lifecycle, Projects, fields/views/iterations, hierarchy/dependency, issue-type, and rate-limit operations. Direct GraphQL is a first-class route, not reduced fallback behavior.
- **High-level approach:** Formalize a capability router for three peer transports: compatible host GitHub integration/MCP, authenticated `gh` GraphQL/REST, and direct GraphQL/REST. Every declared-compatible route must emit the same compact canonical snapshots and use the shared deterministic plan, digest, apply, receipt, and verification engine. Select one complete write route per apply and report missing MCP capabilities explicitly. Use R02/R06 call counts and result shapes to decide whether a thin dedicated MCP adapter is justified; do not duplicate planning logic in that server.
- **Done when:** The representative fixture produces equivalent plans and verified GitHub state through every declared-compatible route; incomplete routes fail capability preflight without partial writes; direct GraphQL remains fully supported; and the dedicated-MCP decision is recorded with token/call evidence.

## Concurrency and dependency plan

### Dependency matrix

| ID | Prerequisites | Can run concurrently with | Shared-code collision risk |
| --- | --- | --- | --- |
| R01 | None | R03, R07 setup, R08, R09 | Medium: overlaps `cli.py`, reconciliation, and tests |
| R02 | Final validation should wait for R01 and R03-R05 | R06, Linux CI, final documentation | Low while executing tests; high if failures require fixes across layers |
| R03 | None | R01, R07 setup, R08, R09 | High with R04/R05: all touch Project discovery, scaffold, GitHub service, and CLI |
| R04 | Agree on the R03 Project/view identity contract | R01, R08, R09; R05 only in isolated branches | High with R03/R05 in `scaffold.py`, `snapshot.py`, `github.py`, and tests |
| R05 | Agree on the R03 Project/field identity contract | R01, R08, R09; R04 only in isolated branches | High with R03/R04 in Project field and snapshot code |
| R06 | Stable release candidate from R01 and R03-R05 | R02, Linux CI, R08 finalization | Low unless evaluations expose skill changes |
| R07 | Repository creation has no code prerequisite; release waits for R02, R06, R08, and R09 | R01, R03-R05, R08, R09 | Low for repository setup; medium for packaging/version files |
| R08 | License choice from the owner | All engineering and evaluation work | Low, except package metadata and README edits |
| R09 | None | R01, R03-R08 | Low if benchmarks are isolated; rerun after behavior changes |
| R10 | R01 safety/journaling contract and an explicit product policy | R11 in isolated branches | High with R11 in sync, mutation, and CLI code |
| R11 | Stable manifest contract; preferably R01 | R10 in isolated branches, R13 evaluation | Medium to high in manifest, mutation, sync, and CLI code |
| R12 | Stable `0.1.0`; portfolio authority decision; lessons from R10/R11 | Design work for R13 | High across schema, IDs, discovery, and planning |
| R13 | Evidence from R02 and R06 | R10/R11 product work after the decision gate | Low if prototyped separately; integration risk is high |

### Recommended execution waves

1. **Wave A - Four parallel foundation lanes — completed 2026-08-27**
   - Lane A: R01 stale-state protection and action journaling — GPT-5.6 Sol, medium reasoning, isolated `wave-a/r01` worktree.
   - Lane B: R03 Project discovery and creation — GPT-5.6 Sol, medium reasoning, isolated `wave-a/r03` worktree.
   - Lane C: R07 repository setup audit — GPT-5.6 Luna, max reasoning, isolated `wave-a/r07` worktree; R08 licensing audit — GPT-5.6 Luna, high reasoning, isolated `wave-a/r08` worktree.
   - Lane D: R09 token benchmark harness and baseline measurements — GPT-5.6 Luna, max reasoning, isolated `wave-a/r09` worktree.
   - Integration reconciled the shared CLI contract and extended R01 fresh-state/journaling guarantees to the newly introduced bootstrap apply path.

2. **Wave B - Project behavior completion — completed 2026-08-27**
   - Lane A: R04 complete view reconciliation — GPT-5.6 Luna, max reasoning, isolated `wave-b/r04` worktree.
   - Lane B: R05 iteration lifecycle — GPT-5.6 Luna, max reasoning, isolated `wave-b/r05` worktree.
   - Lane C: R02 disposable live-evaluation preparation — GPT-5.6 Sol, medium reasoning, isolated `wave-b/r02-prep` worktree; no live GitHub mutations were authorized or performed.
   - Integration retained both full view and iteration configuration in the shared Project queries, aligned the evaluation oracle with the implemented view contract, and added observed iteration state to deterministic sprint expectations.

3. **Wave C - Parallel release-candidate evaluation — completed 2026-09-04**
   - R02 completed through both supported native GitHub transports. The GH CLI and direct-API label-fallback lanes each converge with eight issues, all Project fields/relationships verified, and zero-action second plans; unsupported native-type and generic-MCP routes fail capability preflight before writes.
   - R06 installed-plugin evaluation is complete, including bounded real Codex traces and the deterministic activation/authorization corpus.
   - The R09 100/1,000/10,000-item release-candidate report is unchanged and within every budget. All 163 tests plus build/install/help/benchmark checks pass in a disposable Ubuntu WSL copy; hosted Linux CI remains a Wave D publication gate.

4. **Wave D - Release closure — completed 2026-09-04**
   - R08 known limitations, transport support, safety boundaries, licensing metadata, and legal artifacts were finalized from Wave C evidence.
   - R07 published the canonical public repository, passed hosted Linux CI, protected `main`, and released the exact validated `v0.1.0` tag with wheel and source-distribution assets.
   - The separately approved evaluation cleanup stopped on its first failure after deleting Project #4; no retry or API-target cleanup occurred, and a fresh plan is required for the three remaining resources.

5. **Wave E - Post-release parallel tracks**
   - R10 destructive/reverse reconciliation and R11 import/bulk ingestion may start concurrently after R01, but require isolated branches and a shared authority/conflict contract.
   - Begin R12 only after single-repository behavior and import/reconciliation policies stabilize.
   - Complete R13 transport-parity hardening from R02/R06 evidence, then build a dedicated MCP adapter only if it materially improves capability coverage or token/tool-call efficiency.

### Critical path

```text
(R01 safety) + (R03 Project bootstrap -> R04 views + R05 iterations)
    -> R02 live GitHub evaluation + R06 installed-plugin evaluation
    -> R08 release documentation
    -> R07 tag and publish 0.1.0
```

The `0.1.0` critical path is complete. R09 remained within budget, R02/R06 passed their supported release gates, R08 documentation is final, and R07 publication, hosted Linux CI, branch protection, tagged assets, and clean-checkout verification are complete.

### Concurrency operating rule

The local Git repository now supports isolated worktree development, and Wave A validated that integration pattern. Continue assigning each concurrent lane its own branch/worktree. R04 and R05 still require an agreed Project identity/configuration contract before they run concurrently; R10 and R11 likewise require a shared authority/conflict contract.
