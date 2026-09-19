# Agentic Backlog Kit Roadmap

Last updated: 2026-09-18

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

## Shipped release - `v0.1.0` milestones

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

Continuation ownership and prior-plan status: [active task handoff](docs/task-handoff.md).

**2026-09-18.** The roadmap was re-cut from one flat twenty-item list into
release lines, because the previous structure could not answer "what ships
next". R17 and R18 are implemented and verified, completing the v0.1.1
correctness line in code. R21 begins the first real use of the kit on its own
backlog.

`v0.1.0` remains the published release: hosted `ubuntu-latest` CI passed on
release commit `6a14b70`, `main` has strict `test` protection with administrator
enforcement, and the tag carries validated wheel and source-distribution assets.
The suite now stands at 207 tests, all passing, with byte budgets within
envelope.

First use of the kit on its own backlog converged and produced three new
items. It also found a route asymmetry in the write path: the `gh` CLI route
could never fall back from an unavailable native issue type, because
`gh api` reports every failure as exit code 1 and the fallback keys off an
HTTP 422. The same manifest converged on the direct API route and failed
mid-apply on `gh`. That is fixed here.

Outstanding product work: R15 and R16 (GitHub operational authority, with
policy D1 and carryover policy A already approved) and R11 (adoption).
Outstanding operations work, excluded from the product completion basis: R14
missing-baseline handling with hosted failure-recovery proof, and R20
disposable-resource cleanup. See
[the overall progress report](docs/overall-progress-2026-09-13.md) and
[remediation proposal](docs/remediation-plan.md).

## Release lines

The previous revision of this roadmap ranked R01-R20 as one flat list. That list
mixed shipped scope, speculative features, correctness defects in released code,
release-engineering chores, and disposable-resource cleanup, so its completion
percentage carried no information about product readiness. Work is now grouped
into release lines, each with its own membership and its own denominator.

Lines are named by theme, not by version number. Version numbers are computed
by the organization's release automation from Conventional Commit history, so a
roadmap that predicts them is guessing at an answer it does not own - and it
guessed wrong: the operational-authority line landed as `v0.2.0` and `v0.3.0`
rather than the single `v0.2.0` an earlier revision of this table asserted.
What shipped is recorded after the fact.

| Line | Items | Shipped as | State |
| --- | --- | --- | --- |
| Initial release | M0-M5, R01-R09 | `v0.1.0` | **Shipped** 2026-09-04 |
| Engine correctness | R17, R18 | `v0.1.1` | **Shipped** 2026-09-19 |
| Operational authority | R15, R16 | `v0.2.0`, `v0.3.0` | **Shipped** 2026-09-19 |
| Apply ergonomics | R22, R23 | - | Next; raised by first use |
| Adoption | R11 | - | Not started |
| Reconciliation and reach | R10, R13 | - | Not started |
| Unscheduled | R12, R24 | - | Deferred |
| Continuous | R21 | - | Converged; reporting open |
| Operations | R14, R19, R20 | - | Excluded from product basis |

Two rankings changed deliberately:

- **R17 and R18 moved above all feature work.** They are defects in shipped
  code, not enhancements. R17 in particular was a crash in the deterministic
  engine that is the product's core claim.
- **R11 moved up into its own line, ahead of R10, R12 and R13.** Ingestion
  handles one structured item at a time and only marked issues are managed, so
  without import the kit is usable only on a greenfield repository. For a
  product whose value is managing an existing GitHub backlog, import is the
  gate on adoption by anyone, not a post-release enhancement.

A third line was added after the fact. Apply ergonomics did not come from
planning: R22 and R23 are what first use of the kit on its own backlog exposed,
and they are recorded here rather than folded silently into other work. See
[first-use findings](docs/dogfooding-findings-2026-09-18.md).

Neither shipped line needed a product decision from the owner, and neither does
the adoption line: D1 and carryover policy A were approved before any of this
was written.

## Completion basis

Each line is counted against its own membership. Percentages count items, not
effort, production readiness, or safety approval.

| Basis | Complete | Share |
| --- | --- | --- |
| Initial release milestones M0-M5 | 6/6 | 100% |
| Initial release items R01-R09 | 9/9 | 100% |
| Engine correctness R17-R18 | 2/2 | 100% |
| Apply ergonomics R22-R23 | 0/2 | 0% |
| Operational authority R15-R16 | 2/2 | 100% |
| Adoption R11 | 0/1 | 0% |
| Reconciliation and reach R10, R13 | 0/2 | 0% |
| **Scheduled product work, R01-R23 excluding deferred R12/R24 and operations R14** | **13/16** | **81%** |
| Operations R14, R19, R20 | 1/3 | 33% |

The former headline figure was "9/20 items - 45%". That denominator included
R12, which is explicitly deferred, and three operations chores. The scheduled
product figure above is the number that describes readiness.

That figure fell from 79% to 69% when R22 and R23 were added. Nothing
regressed: the denominator grew because using the product found work that
planning had not. A completion percentage that only ever rises is measuring
the plan rather than the product.

## Work items by release line

Complexity labels describe implementation and validation effort, not importance.

### Shipped in `v0.1.0`

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

### Engine correctness - shipped in `v0.1.1`

Defects in released code.

#### R17 - Support deep dependency graphs without recursion failure

- **Status:** Shipped in `v0.1.1` on 2026-09-19
- **Importance:** Medium
- **Complexity:** Medium
- **Context:** Prioritization and validation both walked the dependency graph recursively. Measured against the shipped v0.1.0 code, `prioritize` raised `RecursionError` from roughly 500 chained items, and `validate_manifest` raised it from roughly 1,200 items when dependencies pointed forward through sorted ids. This roadmap previously recorded the threshold as 1,200 for both; the real prioritization threshold was less than half that.
- **High-level approach:** Completed by replacing both traversals with deterministic iterative algorithms. Cycle detection walks an explicit frame stack over sorted ids and sorted dependencies, so a reported cycle is identical to the one a recursive walk would report. Scoring resolves items in dependent-first order through a released-count queue and sums boosts in the same sorted order, so scores for unfinished work are unchanged. Cycle diagnostics are now bounded, which takes a 5,000-node cycle report from roughly 50 KB to 164 bytes.
- **Done when:** 1,200/10,000-node chains and deep cycles have controlled results across validation and planning; existing mathematical and byte-budget checks remain valid. **Met:** 10,000-node forward and reverse chains validate and prioritize; 5,000-node cycles are still detected and reported compactly; the full suite passes and the benchmark report SHA-256 is unchanged at `0c8e76542847797eda4d30c764476599cc253e1725fd339d889e83df846addf3`.

#### R18 - Enforce zero final scores for completed work

- **Status:** Shipped in `v0.1.1` on 2026-09-19
- **Importance:** Low
- **Complexity:** Easy
- **Context:** Completed work correctly scored a zero *base* score, but the dependency boost still propagated from its dependents into its *final* score. A completed item with two dependents scored 4.0 rather than 0.0, and a completed node relayed a boost to its own prerequisites.
- **High-level approach:** Completed by zeroing the final score of any item in a done status and taking that zero as the propagated contribution, which stops boost relay through completed nodes without a second traversal. Custom done statuses are honoured. Operational status from R15 is not yet available, so this uses manifest status; R15 will supply effective status in operational mode.
- **Done when:** Completed prerequisites score zero for default/custom done statuses, while unfinished graph scores and stable ordering remain correct. **Met:** regression tests cover dependents, boost relay, custom done statuses, and unchanged boosting for unfinished prerequisites; no unfinished score and no documented benchmark value changed.

### Apply ergonomics - next

Raised by first use rather than by planning. Apply is correct but does not
explain itself: a failure names no item, and a completed scaffold can leave the
target unconverged.

#### R22 - Report actionable apply failures

- **Status:** Ready
- **Importance:** High
- **Complexity:** Medium
- **Context:** A failed apply surfaced as `GitHub API error 1: gh: Validation Failed (HTTP 422)`, naming no item, no field and no reason. Diagnosis required reading the receipt for the failing action, querying the organization's issue types by hand, and then reading the transport source. The receipt is good; the operator-facing message is not.
- **High-level approach:** Carry the failing action's item id, endpoint and rejected field into the error the operator sees. Name known causes explicitly, including an unavailable native issue type, and state the fallback actually taken.
- **Done when:** A failed action names the item id and the rejected field, a known cause is named rather than implied, and the remedy or the fallback taken is stated.

#### R23 - Converge a fresh Project in one scaffold apply

- **Status:** Ready
- **Importance:** Medium
- **Complexity:** Medium
- **Context:** `project.view.create` cannot carry a filter, visible-field list, grouping or sorting, so every created view needs an immediate repair pass. Scaffolding a fresh Project reported `completed` at 17 of 17 actions while leaving three views unconverged; convergence arrived only on the third plan. The kit is correct here and never deletes and recreates a view to work around the API boundary, but a `completed` apply that leaves the target unconverged trains the operator to distrust the status.
- **High-level approach:** Either sequence view creation and configuration within one reviewed apply, or state plainly in the plan that a second pass is required and why.
- **Done when:** A fresh Project converges in one reviewed apply, or the plan says a second pass is required; a completed status never implies a converged target when it is not.

### Operational authority - shipped in `v0.2.0` and `v0.3.0`

The kit treated the local manifest as authoritative for operational fields, so
ordinary synchronization reverted what the board recorded and replanning moved
work between sprints on its own. Both product policies were already approved,
so this line was implementation work only.

#### R15 - Respect GitHub operational status and sprint authority

- **Status:** Shipped in `v0.2.0` on 2026-09-19; verified live against Project 6
- **Design note:** [operational authority](docs/operational-authority.md)
- **Importance:** High
- **Complexity:** Hard
- **Approach:** Compose fresh operational state for planning; preserve existing Status/Sprint during ordinary sync; represent changes as explicit digest-bound transitions. Document legacy-manifest migration and offline-preview limits.
- **Done when:** Remote completion/assignment survives stale local intent, planning uses fresh operational state, and explicit transitions fail safely on drift. See R15 acceptance cases in the proposal. **Met:** ordinary sync no longer plans `Status` or `Sprint` writes for work GitHub already tracks; `--transition` and `--transition-sprint` emit digest-bound actions carrying the observed value, and replaying a stale transition plan was refused live; `prioritize`, `next` and `sprint-plan` accept `--operational-snapshot`, report whether they used `github` or `local-intent` state, and surface differences with `--report-operational-drift`. A remote status the manifest does not define is reported and not adopted, because scaffolding appends manifest statuses to GitHub's own and the scoring rules are written in the manifest's vocabulary.
- **Found while verifying:** completed work scoring zero (R18) made it sort last, which held back every item depending on it - `next` returned a lower-value item while the genuinely next story sank. Completed work is now released first so it never delays a dependent, `select_next` takes the highest-scoring executable item rather than the first one dependency order reaches, and the CLI omits completed work from the ranked head unless `--include-completed` is passed. This changed one documented benchmark row; [benchmarks](docs/benchmarks.md) records the new digest.

#### R16 - Preserve sprint commitments and review carryover

- **Status:** Shipped in `v0.3.0` on 2026-09-19
- **Design note:** [sprint commitments](docs/sprint-commitments.md)
- **Importance:** Medium
- **Complexity:** Medium
- **Approach:** Account for retained target-sprint work once, preserve ongoing statuses, and handle work assigned elsewhere through explicit carryover review.
- **Done when:** Replanning neither moves work automatically nor regresses status; capacity, dependencies, overage, and carryover are verified against fresh state. **Met:** work already committed to the target sprint is retained, counted once, and keeps its status, including when it is `Blocked` or not yet ready; work committed to another sprint is withheld from automatic selection however highly it ranks, and moves only when named in `--carryover`; commitments beyond capacity report an explicit `overage` rather than dropping work; and every carryover request is rejected before planning when it names unknown, complete, already-targeted, or unassigned work, or omits a target sprint.
- **Scope note:** commitment is relative to a target, so an untargeted `sprint-plan` ignores sprint assignment and ranks the whole backlog exactly as before. `--skipped-limit` now projects the retained and carryover lists too, which keeps a 10,000-item plan at roughly 8 KB instead of 555 KB.

### Adoption - next after apply ergonomics

The gate on anyone other than the maintainer using the kit.

#### R11 - Import existing backlogs and support bulk ingestion

- **Importance:** Medium
- **Complexity:** Medium
- **Context:** Ingestion handles one structured item at a time and only marked GitHub issues are managed. Adopting an established repository would therefore require significant manual work.
- **High-level approach:** Add a read-only import preview for unmanaged issues, infer candidate types and relationships, detect duplicates, let users review mappings, assign stable ABK IDs, and apply adoption in deterministic batches.
- **Done when:** An existing repository can be imported without modifying unselected issues, duplicate mappings are rejected, and a second import is idempotent.

### Reconciliation and reach

#### R10 - Add destructive and reverse reconciliation

- **Importance:** Medium
- **Complexity:** Hard
- **Context:** Synchronization is deliberately additive and update-only. It does not close deleted work, remove obsolete parents or dependencies, archive Project items, or reconcile remote-only changes back into local intent.
- **High-level approach:** Define authority and conflict policies for every managed field. Introduce explicit destructive action types with stronger confirmations, remote preconditions, soft-delete/archive defaults, recovery information, and comprehensive audit tests.
- **Done when:** Every removal or reverse-sync behavior has an explicit policy, preview, confirmation boundary, audit trail, and recovery path.

#### R13 - Complete native transport parity and decide whether to build a dedicated MCP server

- **Status:** Decision gate opened by Wave C evidence; direct GraphQL works, installed generic GitHub MCP is incomplete for Projects
- **Importance:** High
- **Complexity:** Hard
- **Context:** The product requirement is native GitHub Projects interaction through the Codex GitHub integration/GitHub MCP when it exposes the complete surface, or through direct GraphQL/REST calls. Wave C proved the authenticated CLI and direct API routes can discover and create Projects, while the installed generic GitHub MCP lacks repository lifecycle, Projects, fields/views/iterations, hierarchy/dependency, issue-type, and rate-limit operations. Direct GraphQL is a first-class route, not reduced fallback behavior.
- **High-level approach:** Formalize a capability router for three peer transports: compatible host GitHub integration/MCP, authenticated `gh` GraphQL/REST, and direct GraphQL/REST. Every declared-compatible route must emit the same compact canonical snapshots and use the shared deterministic plan, digest, apply, receipt, and verification engine. Select one complete write route per apply and report missing MCP capabilities explicitly. Use R02/R06 call counts and result shapes to decide whether a thin dedicated MCP adapter is justified; do not duplicate planning logic in that server.
- **Done when:** The representative fixture produces equivalent plans and verified GitHub state through every declared-compatible route; incomplete routes fail capability preflight without partial writes; direct GraphQL remains fully supported; and the dedicated-MCP decision is recorded with token/call evidence.

### Unscheduled

#### R24 - Reconsider hierarchy expressiveness for small work

- **Status:** Inbox; recorded, not scheduled
- **Importance:** Low
- **Complexity:** Medium
- **Context:** The hierarchy is a strict ladder and a parent must be exactly one level above its child, so a small chore directly under a Feature has no type: `Task` is reserved for level 5 under a `Story` or `Bug`. Six decomposed items in the kit's own backlog were written as Tasks and had to be retyped as Stories, which overstates them.
- **High-level approach:** Decide whether the strict ladder is intentional. If it is, document why; if it is not, consider permitting a Task directly under a Feature.
- **Done when:** A decision is recorded either way with its modeling rationale.

#### R12 - Support multi-repository portfolio planning

- **Importance:** Later
- **Complexity:** Hard
- **Context:** One manifest currently targets one repository and one organization Project. Cross-repository initiatives and dependencies are outside the current authority model.
- **High-level approach:** Separate portfolio items from repository-owned delivery items, introduce repository-qualified stable references, support cross-repository dependencies, and retain compact per-repository snapshots.
- **Done when:** Multiple repositories can participate in one portfolio Project without ID ambiguity or loading every repository backlog into model context.

### Continuous

#### R21 - Run the kit against its own backlog

- **Status:** Converged on 2026-09-18; reporting remains open
- **Importance:** High
- **Complexity:** Easy
- **Context:** The kit had never been pointed at its own work. The repository carried zero GitHub issues, no manifest, and no managed Project; the only applies ever performed were against disposable evaluation fixtures. Meanwhile this roadmap maintained twenty-one work items with importance, complexity, dependencies, and status by hand in one large Markdown file - exactly the artifact the kit exists to manage.
- **High-level approach:** Express the release lines and open work items as a tracked manifest, then drive the ordinary `init -> scaffold -> sync` lifecycle against a real Project. Treat the roadmap prose as human-readable rationale and the manifest as machine-readable intent. Record every defect this surfaces against the responsible work item rather than patching around it, because first-use friction is the point.
- **Done when:** A tracked manifest describes the open roadmap, a scaffolded Project reflects it, a second sync plan contains zero actions, and the friction encountered is written up against the responsible work item.
- **Known cost:** Dogfooding before R15 lands means local intent overwrites GitHub `Status` and `Sprint` on ordinary sync. That is accepted deliberately: it produces the acceptance evidence R15 and R16 need.
- **Result:** [Organization Project 6](https://github.com/orgs/aegolius-labs/projects/6) holds 50 items; the repository holds 50 issues with sub-issue and dependency links. Scaffold converged across three plans (17, 3, 0 actions) and sync across three (169 with a failure at 31, 139, 0), then an incremental 23-action pass converged again. Ten findings are recorded in [first-use findings](docs/dogfooding-findings-2026-09-18.md); two were fixed here, two became R22 and R23, and one became R24.

## Operations checklist

These items are release plumbing and resource cleanup. They are tracked because
they are real and unfinished, but they are **excluded from the product
completion basis**: none of them changes what the kit does for a user, and
counting them alongside product work is what made the previous percentage
misleading.

#### R14 - Adopt organization-managed semantic releases

- **Status:** Ongoing. Shared/caller correction merged; hosted no-bump and Plan L immutable publication/download/install checks passed. Missing-baseline guard (R14-F7) and hosted draft/partial-upload recovery remain, and R14-F8 was found on 2026-09-19.
- **R14-F8 - the packaged version is not synchronized with the computed version (fixed 2026-09-19):** the first real release-bearing merge computed `v0.1.1` while `pyproject.toml`, both plugin manifests, the marketplace entry, and `__init__.py` still declared `0.1.0`. Preflight refused with `tag 'v0.1.1' does not match package version '0.1.0'`, and no tag, draft, or asset was created - the fail-closed contract held exactly as intended. But it means every release-bearing merge fails until a human bumps five declarations and adds a CHANGELOG entry by hand, which is the opposite of delegating version calculation to the organization. Several release tests also hardcoded the current version, so a bump required editing tests. **Fixed:** `scripts/set_version.py` stamps the computed version across all five declarations and promotes the changelog's Unreleased section, and release preflight runs it against the candidate checkout before building. Nothing is committed or pushed - the tag stays the record of what a version means - so the computed version reaches the package without anyone predicting it. Contributors write under `## [Unreleased]` and the release stamps the heading.
- **Importance:** High
- **Complexity:** Medium
- **Context:** The initial release used a repository-specific tag workflow. Aegolius Labs repositories are expected to delegate semantic version calculation, tagging, and GitHub Release creation to the reusable workflows maintained in `aegolius-labs/.github`.
- **High-level approach:** Added organization-owned `compute-release.yml` with read-only permission and `publish-release-assets.yml` with a draft-first publisher, preserving the existing no-asset workflow. Bind preflight to the candidate SHA/tag and exact distributions; create a draft, attach and verify assets, then publish. Preserve organization ownership of tagging and releases. See [R14 design and reference-project comparison](docs/remediation-plan.md#r14-repair-shared-release-integration-f1f2).
- **Done when:** The shared interface and caller pass permission/identity/recovery contract tests; hosted no-bump and separately authorized immutable-release evaluations pass; then protected publication and exact asset verification are recorded. Local test success alone is insufficient.

#### R19 - Publish accurate release and remediation status

- **Status:** Complete. Wave D/remediation documentation published in PRs #1/#2, and the 2026-09-13 evaluation/status refresh is present on `origin/main` (verified 2026-09-18: `main` is in sync with `origin/main`, no unpushed commits). The previous 'awaits publication' status was stale.
- **Importance:** Medium
- **Complexity:** Easy
- **Approach:** Prepare documentation separately from unresolved R14 code; publish through the protected-branch process after applicable authorization.
- **Done when:** Public main documents the completed v0.1.0 release and outstanding corrective work; readback at the published SHA is recorded. Do not rewrite the release tag.

#### R20 - Resolve remaining disposable evaluation resources

- **Status:** Pending fresh identity discovery and separately confirmed cleanup plan.
- **Importance:** Low; not a release blocker
- **Complexity:** Easy, subject to permissions
- **Approach:** Refresh exact identities from the prior receipt, confirm absence of Project #4, plan only remaining resources, and stop/journal on first failure.
- **Done when:** Remaining resources are verified absent or the owner explicitly elects retention. No deletion is authorized by this proposal.

## Historical concurrency and dependency plan (Waves A-E)

The wave plan below records how R01-R14 were sequenced and executed. It is
retained as the delivery record for the shipped release. It does not govern the
release lines above; those are sequenced by the dependency notes in each line.


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
| R10 | R01, R15/R16 operational correctness, and explicit destructive policy | R11 in isolated branches | High with R11 in sync, mutation, and CLI code |
| R11 | R15/R16 authority and commitment contract; stable manifest migration | R10 in isolated branches, R13 evaluation | Medium to high in manifest, mutation, sync, and CLI code |
| R12 | Stable `0.1.0`; portfolio authority decision; lessons from R10/R11 | Design work for R13 | High across schema, IDs, discovery, and planning |
| R13 | Evidence from R02 and R06 | R10/R11 product work after the decision gate | Low if prototyped separately; integration risk is high |
| R14 | New validated organization compute/publish interface | R15-R18, R19 documentation preparation | Shared release workflow and ABK caller/tests |
| R15 | Approved D1; R01 freshness contract | R14, R17/R18 with coordinated integration | High across snapshot, CLI, sync, and planning |
| R16 | R15; approved D2 (A) | R14, R19 | High with R15 in sprint/CLI/skills |
| R17 | Existing score/ordering contract | R14, R15 with coordinated integration | High with R18 in priority code |
| R18 | Zero-score rule; integrate with R17 and R15 effective state | R14, R19 | High with R17 in priority code |
| R19 | Verified Wave D evidence; authorized protected publication | R14-R18 preparation | Documentation conflicts; keep separate from unresolved workflow |
| R20 | Fresh identities and new destructive digest confirmation | Other work | Separate cleanup evidence; no product runtime changes |

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
   - R14 corrections are merged; 185 ABK tests and 18 shared tests passed in the prior validation. Hosted no-bump and Plan L immutable publication/download/install evidence now pass. Complete the missing-baseline guard and hosted failure-recovery evaluation before closure.
   - Complete R15 operational authority and R16 commitment/carryover correctness before R10 destructive work or R11 import. R17/R18 graph/scoring fixes may proceed independently with coordinated integration.
   - Publish accurate status through R19; keep separately confirmed R20 cleanup off the product critical path.
   - Begin R12 only after single-repository behavior and import/reconciliation policies stabilize.
   - Complete R13 transport-parity hardening from R02/R06 evidence, then build a dedicated MCP adapter only if it materially improves capability coverage or token/tool-call efficiency.

### Critical path

Wave E: validated shared release extension -> repaired R14 caller -> hosted proof;
D1/D2 approved -> R15/R16 -> R10/R11 -> R12. R17/R18 must pass
their regression gates before a corrective product release. R19 documentation
publication is separate; R20 cleanup does not block it.

Historical v0.1.0 delivery path:

```text
(R01 safety) + (R03 Project bootstrap -> R04 views + R05 iterations)
    -> R02 live GitHub evaluation + R06 installed-plugin evaluation
    -> R08 release documentation
    -> R07 tag and publish 0.1.0
```

The `0.1.0` critical path is complete. R09 remained within budget, R02/R06 passed their supported release gates, R08 documentation is final, and R07 publication, hosted Linux CI, branch protection, tagged assets, and clean-checkout verification are complete.

### Concurrency operating rule

The local Git repository now supports isolated worktree development, and Wave A validated that integration pattern. Continue assigning each concurrent lane its own branch/worktree. R04 and R05 still require an agreed Project identity/configuration contract before they run concurrently; R10 and R11 likewise require a shared authority/conflict contract.
