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

**2026-09-21.** R15, R16, R11, R22 and R23 have since shipped, and R13 closed
with the dedicated-MCP decision recorded as no. GH-63 lands here: adoption now
proposes the sub-issue and dependency structure GitHub already records instead
of flattening it, which also closes a divergence, because additive
synchronization never removed the relationships a flat adoption denied.

**2026-09-24.** The owner decided the three open questions. R25 is approved
with a concrete design and is the next item. R10 is reframed from destructive
and reverse reconciliation to closing the work lifecycle from evidence, and
decomposed into four stories. R20 deletes four resources and retains the
release fixture.

**2026-09-24, later.** R25 shipped in v0.11.0. A
[production readiness report](docs/production-readiness-2026-09-24.md) found the
engine ready and the product not: 3 of 12 gates met and 3 partly met. The gaps are
filed as R28-R34 under `EPIC-PROD`, and the owner put scale ahead of R10.

Outstanding product work: **R28** and **R29** (scale and GitHub lag), then
installation and evaluation (**R30**-**R32**), then **R10**, then the stability
policy and an outside pilot (**R33**, **R34**). Outstanding operations work,
excluded from the product completion basis: R20 disposable-resource cleanup,
blocked until the owner grants a token with `delete_repo`. R14 closed on 2026-09-24
when Plan M proved hosted draft/partial-upload recovery against the retained
release fixture. See
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
| Apply ergonomics | R22, R23 | `v0.4.0` | **Shipped** 2026-09-19; raised by first use |
| Adoption | R11 | `v0.5.0` | **Shipped** 2026-09-19 |
| Reconciliation and reach | R10, R13, GH-63, R25 | pending | R13 and GH-63 complete; R25 ready, R10 refined into four stories |
| Planning and handoff | R26, R27 | pending | Both complete; see the generated [schedule projection](docs/roadmap-gantt.md) |
| Production readiness | R28-R34 | pending | Filed 2026-09-24 from the [readiness report](docs/production-readiness-2026-09-24.md); scale first |
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
| Apply ergonomics R22-R23 | 2/2 | 100% |
| Operational authority R15-R16 | 2/2 | 100% |
| Adoption R11 | 1/1 | 100% |
| Reconciliation and reach R10, R13, GH-63, R25 | 2/4 | 50% |
| Planning and handoff R26, R27 | 2/2 | 100% |
| **Scheduled product work** - R01-R11, R13, R15-R18, R22, R23, GH-63, R25-R27 | **20/22** | **91%** |
| Operations R14, R19, R20 | 2/3 | 67% |

The former headline figure was "9/20 items - 45%". That denominator included
R12, which is explicitly deferred, and three operations chores. The scheduled
product figure above is the number that describes readiness.

R10 and R13 are the two scheduled items still open, which is why this figure
is 89% rather than 100%. An earlier revision of this table said 16/16; that
was arithmetic that quietly dropped them, and a completion basis that loses
its own open items is worse than no basis at all.

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

### Apply ergonomics - shipped in `v0.4.0`

Raised by first use rather than by planning. Apply is correct but does not
explain itself: a failure names no item, and a completed scaffold can leave the
target unconverged.

#### R22 - Report actionable apply failures

- **Status:** Shipped in `v0.4.0` on 2026-09-19
- **Importance:** High
- **Complexity:** Medium
- **Context:** A failed apply surfaced as `GitHub API error 1: gh: Validation Failed (HTTP 422)`, naming no item, no field and no reason. Diagnosis required reading the receipt for the failing action, querying the organization's issue types by hand, and then reading the transport source. The receipt is good; the operator-facing message is not.
- **High-level approach:** Carry the failing action's item id, endpoint and rejected field into the error the operator sees. Name known causes explicitly, including an unavailable native issue type, and state the fallback actually taken.
- **Done when:** A failed action names the item id and the rejected field, a known cause is named rather than implied, and the remedy or the fallback taken is stated. **Met:** every apply path records a `hint` in its receipt alongside the failing action, and the CLI prints a structured JSON error with that hint on stderr and exits non-zero instead of raising a traceback. Hints cover the causes first use actually hit - an unavailable native issue type names the type, the remedy and the label that would be used instead; permission, absence and rate-limit failures name what to do next - and stay silent rather than guessing at an unknown cause.

#### R23 - Converge a fresh Project in one scaffold apply

- **Status:** Shipped in `v0.4.0` on 2026-09-19, by the second of its two acceptable outcomes
- **Importance:** Medium
- **Complexity:** Medium
- **Context:** `project.view.create` cannot carry a filter, visible-field list, grouping or sorting, so every created view needs an immediate repair pass. Scaffolding a fresh Project reported `completed` at 17 of 17 actions while leaving three views unconverged; convergence arrived only on the third plan. The kit is correct here and never deletes and recreates a view to work around the API boundary, but a `completed` apply that leaves the target unconverged trains the operator to distrust the status.
- **High-level approach:** Either sequence view creation and configuration within one reviewed apply, or state plainly in the plan that a second pass is required and why.
- **Done when:** A fresh Project converges in one reviewed apply, or the plan says a second pass is required; a completed status never implies a converged target when it is not. **Met by the second clause.** GitHub's view-creation input does not accept a filter, visible fields, grouping or sorting, and the kit will not delete and recreate a view to work around that boundary, so a newly created view genuinely cannot converge in the apply that creates it. A plan containing any `project.view.create` now reports `converges_in_one_apply: false` with a `follow_up` explaining why and what to run next, and the completed apply receipt carries the same note. Hiding the boundary behind a silent retry would misreport what the API can do.

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

### Adoption - shipped in `v0.5.0`

The gate on anyone other than the maintainer using the kit.

#### R11 - Import existing backlogs and support bulk ingestion

- **Status:** Shipped in `v0.5.0` on 2026-09-19; verified live by adopting issue #63
- **Design note:** [adopting an existing backlog](docs/importing.md)
- **Importance:** Medium
- **Complexity:** Medium
- **Context:** Ingestion handles one structured item at a time and only marked GitHub issues are managed. Adopting an established repository would therefore require significant manual work.
- **High-level approach:** Add a read-only import preview for unmanaged issues, infer candidate types and relationships, detect duplicates, let users review mappings, assign stable ABK IDs, and apply adoption in deterministic batches.
- **Done when:** An existing repository can be imported without modifying unselected issues, duplicate mappings are rejected, and a second import is idempotent. **Met:** `import-plan` reads and writes nothing and reports why every unproposed issue was left out; `import-apply` adopts only the reviewed plan, prepending the marker and preserving the existing body, and touches no other issue; a colliding id is refused outright while a colliding title is withheld unless explicitly allowed; and a marked issue is no longer unmanaged, so a second plan proposes nothing. Verified live end to end: issue #63 was adopted, and the next sync plan recognised it as existing rather than creating a duplicate.
- **Found while verifying:** adoption marks GitHub before the manifest records the item, and the first live run failed in between, stranding the issue as managed on GitHub and unknown locally. `import-plan` now reports such `orphans` and `import-reconcile` repairs them locally, because GitHub is already correct. The ordering cannot be inverted: writing the manifest first would make synchronization create duplicates if the GitHub write then failed.
- **Deliberately out of scope:** hierarchy and dependency inference, which costs an extra request per issue. Tracked as the adopted issue #63 itself.

### Reconciliation and reach

#### R10 - Close the work lifecycle from evidence

- **Status:** Refined 2026-09-24 by owner decision; decomposed into S-R10-1 to S-R10-4.
- **Importance:** Medium
- **Complexity:** Medium
- **Context:** Synchronization is deliberately additive and update-only. As first written, R10 would have added closing deleted work, removing relationships, archiving Project items, and reconciling remote changes back into local intent. aio-agentic-sdlc's authority model cites the absence of exactly those operations as what makes the projection one-way, and GitHub state must come back as evidence, never as intent.
- **Decision (2026-09-24):** automate the lifecycle from evidence, never from the manifest's silence. GitHub already closes an issue when a PR carrying `Closes #N` merges, and Project 6's built-in workflows then mark it Done. That is evidence-based and stays GitHub's job. The kit makes it dependable, finishes the loop where the evidence is unambiguous, and never closes, deletes, or archives an issue because the manifest stopped listing it. Pulling GitHub edits back into the manifest is dropped from scope.
- **Stories:**
  - S-R10-1 - the skills tell agents to link each PR to the kit issues it completes with a closing keyword.
  - S-R10-2 - propose closing a parent once every child is closed, through plan, digest confirmation, apply, and receipt.
  - S-R10-3 - remove parent and dependency links the manifest no longer declares, between kit-managed issues only, with recovery information; amend the authority model in the same change.
  - S-R10-4 - a plan made only of Priority field updates is recognized by the engine and applied without a separate confirmation. The owner pre-authorized this on 2026-09-24.
- **Done when:** All four stories are verified, and no path closes, deletes, or archives an issue because it is absent from the manifest.

#### R13 - Complete native transport parity and decide whether to build a dedicated MCP server

- **Status:** Complete on 2026-09-19; the dedicated-MCP decision is recorded as **no**
- **Design note:** [transport parity and the dedicated-MCP decision](docs/transport-parity.md)
- **Importance:** High
- **Complexity:** Hard
- **Context:** The product requirement is native GitHub Projects interaction through the Codex GitHub integration/GitHub MCP when it exposes the complete surface, or through direct GraphQL/REST calls. Wave C proved the authenticated CLI and direct API routes can discover and create Projects, while the installed generic GitHub MCP lacks repository lifecycle, Projects, fields/views/iterations, hierarchy/dependency, issue-type, and rate-limit operations. Direct GraphQL is a first-class route, not reduced fallback behavior.
- **High-level approach:** Formalize a capability router for three peer transports: compatible host GitHub integration/MCP, authenticated `gh` GraphQL/REST, and direct GraphQL/REST. Every declared-compatible route must emit the same compact canonical snapshots and use the shared deterministic plan, digest, apply, receipt, and verification engine. Select one complete write route per apply and report missing MCP capabilities explicitly. Use R02/R06 call counts and result shapes to decide whether a thin dedicated MCP adapter is justified; do not duplicate planning logic in that server.
- **Done when:** The representative fixture produces equivalent plans and verified GitHub state through every declared-compatible route; incomplete routes fail capability preflight without partial writes; direct GraphQL remains fully supported; and the dedicated-MCP decision is recorded with token/call evidence. **Met:** action kinds declare their required capabilities and transports declare what they provide, so all five apply paths refuse before their first write when the selected route cannot finish, naming every missing capability; `abk capabilities` reports a route without planning anything; both peer routes are driven through the same service in parity tests; and direct GraphQL is documented and typed as a peer rather than a fallback.
- **Decision: do not build a dedicated MCP server.** An MCP tool returns its result to the model, so routing discovery through one would put a 75 KB / 753 KB / 7.5 MB snapshot into context and undo R09; a cold sync of 1,000 items is 2,220 write calls and roughly 2,001 reads, which belongs in a journaled loop rather than a conversation; and a third route is a third route to hold at parity, which broke twice in a single day of real use. Revisit triggers are recorded in the design note.
- **Found while verifying:** after the earlier narrow 422 fix, a 403, 429 or 500 still reported as exit code 1 on the CLI route, so R22's hints fired on the API route and never on `gh`. The parity test found it. The reported status is now taken as the status, except that a 404 is mapped only for the exact parent-absence pair, because `GET .../parent` also answers 404 when the issue itself is absent.

#### GH-63 - Infer hierarchy and dependencies when importing existing issues

- **Status:** Complete. Shipped in `v0.7.0` on 2026-09-22 and live-validated the
  same day against a disposable fixture; see
  [live validation](docs/adoption-live-validation-2026-09-22.md)
- **Importance:** High
- **Complexity:** Medium
- **Context:** R11 adopted an existing issue flat: neutral type, `parent: null`,
  `depends_on: []`. GitHub already records the sub-issue parent and the
  `blocked_by` dependencies, and synchronization is additive, so it never
  removed the relationships the manifest claimed did not exist. An adopted
  repository therefore kept a structure on GitHub that local intent denied, and
  nothing reconciled the two. This item is the reason import was usable only as
  a flat dump of an existing backlog.
- **High-level approach:** `read_unmanaged(with_relationships=True)` reads the
  parent and the `blocked_by` set per unmanaged issue, and
  `import-plan --infer-relationships` proposes them. Opt-in, because it costs
  two extra reads per issue. A relationship the manifest cannot express is
  withheld with its reason rather than forced, and the plan records which mode
  built it so apply rebuilds and re-digests the same way.
- **Done when:** An import proposes the parent and dependency structure GitHub
  records; a relationship outside the hierarchy ladder, outside the adoption,
  or closing a dependency cycle is reported rather than applied; the default
  read cost is unchanged; and a plan whose mode was edited after review is
  refused. **Met**, in unit tests and then against
  `aegolius-labs/abk-adopt-eval-20260922`: three parents and three dependencies
  proposed from real GitHub structure, two parents withheld with accurate
  reasons, a narrowed adoption withholding only its outside references, the
  orphan reason and its `import-reconcile` recovery working end to end, apply
  completing 9/9 against the reviewed digest, and a second plan proposing
  nothing. Seven of nine adopted items then matched GitHub's structure exactly;
  the two that did not were the deliberate withholdings.
- **Found while validating:** GitHub itself refuses to create a dependency
  cycle, so the cycle-withholding branch cannot be reached through its own
  `blocked_by` graph. It still fires when a dependency resolves onto an
  already-managed item whose `depends_on` closes a loop, so it is not dead code,
  but its trigger is narrower than the design assumed and it stays covered by
  unit tests rather than by that run. Recorded rather than quietly claimed as
  exercised.
- **Withheld rather than forced:** a repository whose issue types are outside
  the manifest's hierarchy adopts as `Task` throughout, and `Task` cannot
  parent `Task`, so its whole structure reports as withheld. That is the strict
  ladder R24 is open about, surfaced by real use rather than argued about.

#### R25 - Carry a canonical GUID through to GitHub for Seam A traceability

- **Status:** Implemented 2026-09-24. The aio-agentic-sdlc counterpart fixture
  is in [aio-agentic-sdlc#103](https://github.com/aegolius-labs/aio-agentic-sdlc/pull/103)
  and closes the last acceptance criterion when it merges. Filed 2026-09-22 through this
  kit's own backlog as
  [#69](https://github.com/aegolius-labs/agentic-backlog-kit/issues/69), design
  approved by the owner on 2026-09-24
- **Approved design:** an optional item field `guid` holding a canonical
  lowercase UUID, validated exactly as aio-agentic-sdlc canonicalizes it.
  Manifest `schema_version` becomes 2 with a tested migration from 1. The marker
  gains `;guid=<uuid>` only on items that carry one and keeps `schema=1`: older
  parsers read the id only up to the first `;`, so existing bodies need no
  rewrite. An older kit that rewrites a body drops the key; that limit is
  documented rather than engineered around.
- **Importance:** High as an enabler; nothing today depends on it
- **Complexity:** Medium
- **Context:** `aio-agentic-sdlc/doc/authority-model.md` requires that a
  canonical GUID be carried into the ABK item and into the GitHub issue body
  marker, so a projected issue can always be traced back to its Intention DAG
  node. This kit cannot. `$defs.item` sets `additionalProperties: false` over a
  fixed fourteen-field list with no GUID field, and the marker
  `<!-- agentic-backlog-kit:id=<id>;schema=1 -->` has room for a second key that
  nothing writes or reads. Seam B is implemented and pinned by fixtures on both
  sides; Seam A is documented and unbuilt, and neither repository references the
  other in `src` or `tests`.
- **High-level approach:** An optional GUID on the item under a bumped schema
  version with a tested migration from version 1, carried into the marker, plus
  a Seam A fixture committed on each side so neither repository imports the
  other to test the contract.
- **Done when:** An item can carry a GUID and one without stays valid, because
  standalone use owns no Intention DAG; the marker round-trips it through read
  and adoption; and both fixtures exist.
- **Why now rather than when the framework arrives:** adding the carrier later
  costs a schema bump, a marker extension, and a re-link pass over every issue
  created before it. That is cheap at fifty issues and expensive at five
  thousand. Standalone use is a supported configuration, so this blocks nothing
  today - it only gets more expensive.

### Planning and handoff

The theme is one requirement: a backlog must be pickupable by whoever arrives
next, who did not watch the last session work. See
[handoff](docs/handoff.md).

#### R26 - Make the next task answerable by the kit rather than by prose

- **Status:** Complete on 2026-09-22
- **Importance:** High
- **Complexity:** Easy
- **Context:** `next` returned one id and silently discarded everything ranked
  above it - container types, completed work, explicit blocks, unrefined
  maturity, and unmet dependencies all dropped without a record. An operator saw
  an answer that looked wrong and could not tell why. The cost was paid by prose
  instead: every activation checkpoint in `docs/task-handoff.md` restated a
  ranking by hand and every one went stale, the 2026-09-22 one naming an item
  that shipped the same day.
- **Done when:** `next --explain N` names what it passed over and why; completed
  work is not reported as an obstacle; `select_next` is unchanged for its
  callers; and a tracked document states that a handoff may not restate anything
  the kit can compute. **Met.**

#### R27 - Project the backlog onto a timeline and render a Gantt chart

- **Status:** Complete on 2026-09-22
- **Importance:** High
- **Complexity:** Medium
- **Context:** The manifest already carries effort, a proven-acyclic dependency
  graph, computed priority and an iteration start date - everything a schedule
  needs - and sequence over time still had to be reconstructed by hand, which is
  the artifact this kit exists to replace.
- **Done when:** the schedule is deterministic and dependency-respecting;
  concurrency never reorders a dependency; exclusions are reported with reasons;
  rendering adds no runtime dependency; every chart states its basis and that it
  is a projection rather than an estimate; and the committed projection is
  guarded by a test. **Met.** See [scheduling](docs/scheduling.md).
- **Found while building it:** a container is excluded because its children
  carry the work, but a container with *no* children is the largest thing left,
  and excluding it projected this roadmap's undecomposed features onto an empty
  timeline. A childless container is now scheduled.

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

- **Status:** Complete 2026-09-24. Shared/caller correction merged; hosted no-bump and Plan L immutable publication/download/install checks passed. R14-F8 was found and fixed on 2026-09-19, the missing-baseline guard (R14-F7) landed on 2026-09-19, and Plan M proved hosted draft/partial-upload recovery on 2026-09-24.
- **R14-F8 - the packaged version is not synchronized with the computed version (fixed 2026-09-19):** the first real release-bearing merge computed `v0.1.1` while `pyproject.toml`, both plugin manifests, the marketplace entry, and `__init__.py` still declared `0.1.0`. Preflight refused with `tag 'v0.1.1' does not match package version '0.1.0'`, and no tag, draft, or asset was created - the fail-closed contract held exactly as intended. But it means every release-bearing merge fails until a human bumps five declarations and adds a CHANGELOG entry by hand, which is the opposite of delegating version calculation to the organization. Several release tests also hardcoded the current version, so a bump required editing tests. **Fixed:** `scripts/set_version.py` stamps the computed version across all five declarations and promotes the changelog's Unreleased section, and release preflight runs it against the candidate checkout before building. Nothing is committed or pushed - the tag stays the record of what a version means - so the computed version reaches the package without anyone predicting it. Contributors write under `## [Unreleased]` and the release stamps the heading.
- **Importance:** High
- **Complexity:** Medium
- **Context:** The initial release used a repository-specific tag workflow. Aegolius Labs repositories are expected to delegate semantic version calculation, tagging, and GitHub Release creation to the reusable workflows maintained in `aegolius-labs/.github`.
- **High-level approach:** Added organization-owned `compute-release.yml` with read-only permission and `publish-release-assets.yml` with a draft-first publisher, preserving the existing no-asset workflow. Bind preflight to the candidate SHA/tag and exact distributions; create a draft, attach and verify assets, then publish. Preserve organization ownership of tagging and releases. See [R14 design and reference-project comparison](docs/remediation-plan.md#r14-repair-shared-release-integration-f1f2).
- **Done when:** The shared interface and caller pass permission/identity/recovery contract tests; hosted no-bump and separately authorized immutable-release evaluations pass; then protected publication and exact asset verification are recorded. Local test success alone is insufficient.
- **R14-F7 closed on 2026-09-19:** a `baseline-guard` job runs on exactly the runs preflight does not, so no calculator outcome is unexamined. It fails a no-bump that has no version tag behind it, passes one that does, and never creates a tag - where version history starts is a decision, not a default. The contract rejects removing the guard, granting it write access, inverting its condition, dropping its check, letting it run `git tag`, or giving it a shallow checkout that would hide the tags it judges by.
- **Hosted recovery proven on 2026-09-24 (S-R14-2):** approved Plan M cancelled a fixture `v0.1.1` release run before its publisher wrote anything, placed a tag, a marked draft and the wheel alone from the run's own bundle, then re-ran the failed job. The publisher accepted the draft, verified the wheel, uploaded only the sdist and published an immutable release; its receipt records no tag or draft creation and no replacement. The partial state was operator-written, because the publisher has no fault-injection hook - see [the evidence](docs/validation.md#r14-hosted-recovery-after-draft-creation-and-partial-upload-2026-09-24) for exactly what this does and does not prove.

#### R19 - Publish accurate release and remediation status

- **Status:** Complete. Wave D/remediation documentation published in PRs #1/#2, and the 2026-09-13 evaluation/status refresh is present on `origin/main` (verified 2026-09-18: `main` is in sync with `origin/main`, no unpushed commits). The previous 'awaits publication' status was stale.
- **Importance:** Medium
- **Complexity:** Easy
- **Approach:** Prepare documentation separately from unresolved R14 code; publish through the protected-branch process after applicable authorization.
- **Done when:** Public main documents the completed v0.1.0 release and outstanding corrective work; readback at the published SHA is recorded. Do not rewrite the release tag.

#### R20 - Resolve remaining disposable evaluation resources

- **Status:** Fresh discovery done 2026-09-24 (S-R20-1); awaiting the owner's
  per-resource choice between retention and a separately confirmed deletion
  plan. Project #4 is verified absent. Five resources remain, each identified by
  node ID in [the discovery record](docs/validation.md#r20-fresh-resource-discovery-2026-09-24):
  the two Wave C repositories and Project #5 from the original receipt, plus the
  adoption and release fixtures below. Repository deletion needs a token with
  `delete_repo`, which the current one lacks. One resource was added on 2026-09-22 and its identity is recorded rather
  than left to be rediscovered: `aegolius-labs/abk-adopt-eval-20260922`, private,
  created for the GH-63 live validation and retained because the authenticated
  token carries no `delete_repo` scope. Deleting it needs a token that does, and
  it is safe to delete - nothing references it but
  [the validation record](docs/adoption-live-validation-2026-09-22.md).
  The public release fixture `aegolius-labs/abk-release-eval-20260908` gained
  tag `v0.1.1` and immutable release `395291910` on 2026-09-24 for the R14
  recovery proof; they are evaluation assets, recorded in
  [validation.md](docs/validation.md#r14-hosted-recovery-after-draft-creation-and-partial-upload-2026-09-24).
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
   - R14 corrections are merged; 185 ABK tests and 18 shared tests passed in the prior validation. Hosted no-bump and Plan L immutable publication/download/install evidence pass, the missing-baseline guard landed on 2026-09-19, and Plan M proved hosted failure recovery on 2026-09-24. R14 is closed.
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
