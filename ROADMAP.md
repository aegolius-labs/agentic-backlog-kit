# Agentic Backlog Kit Roadmap

Last updated: 2026-08-27

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
- GitHub access may use an available GitHub MCP server, GitHub CLI, or direct API. Skills choose the best available route, while the local engine remains provider-neutral.
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
- [x] Support GitHub MCP as the preferred interactive route when matching tools are available.

### M4 - Backlog and sprint scaffolding

- [x] Scaffold labels, issue types or fallback type labels, Project fields, and standard statuses.
- [x] Create backlog table, Kanban board, sprint board, and roadmap views.
- [x] Create or select iterations and assign a dependency-valid sprint slice.
- [x] Add example manifests and a safe demo workflow.
- [x] Create or discover the organization Project during first-run setup (R03).
- [ ] Reconcile complete filters, grouping, sorting, and other view configuration (R04).
- [ ] Manage current, next, completed, and rolling iterations (R05).

### M5 - Release readiness

- [x] Run plugin and skill validators.
- [ ] Run the complete test suite on a CI Linux runner; the Windows suite is green locally.
- [x] Add GitHub Actions for tests and package validation.
- [x] Build and inspect the Python package and add a tag-driven GitHub release workflow.
- [x] Select the noncommercial/paid-commercial licensing model and add release, support, security, and contribution documentation (R08).
- [ ] Perform realistic dry-run and apply evaluations against a disposable repository/project.
- [ ] Evaluate the installed plugin and skill activation through Codex (R06).
- [x] Measure and enforce token-efficiency budgets (R09).
- [ ] Publish an initial `0.1.0` release and document known limitations.

## Current checkpoint

Wave A completed on 2026-08-27. The repository is initialized locally, all 74 Windows tests pass, the 100/1,000/10,000-item byte-budget gate passes, the CLI and built wheel pass smoke checks, and the official plugin plus all five skill validators pass. R01 fresh-state protection and journaling, R03 Project bootstrap, R08 licensing/release documentation, R09 benchmarks, and the local setup portion of R07 are complete. Remote publication, Linux CI execution, R04/R05 Project behavior, R02 live GitHub evaluation, R06 installed-plugin evaluation, and the final tag/release remain open.

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

- **Status:** Not started; scheduled for Wave C
- **Importance:** Critical
- **Complexity:** Hard
- **Context:** The 74 tests use local or simulated GitHub responses. No complete workflow has yet created and reconciled real issues, sub-issues, dependencies, Project fields, iterations, or views.
- **High-level approach:** Create a disposable organization repository and Project. Exercise initialization, scaffolding, ingestion, prioritization, sprint planning, apply, and post-apply convergence through GitHub CLI, direct API, and GitHub MCP. Test native issue types and label fallback independently.
- **Done when:** Each supported executor completes the representative workflow, the second plan contains zero actions, failure cases are recorded, and the resulting GitHub state matches the manifest and view contracts.

#### R03 - Complete first-run Project creation and discovery

- **Status:** Complete in Wave A
- **Importance:** High
- **Complexity:** Hard
- **Context:** `init-plan` now discovers organization Projects by exact number/title or unique repository association, fails closed on ambiguity, and plans explicit creation when none exists. `init-apply` captures and persists Project identity, refreshes GitHub, and produces the separately reviewed scaffold plan.
- **High-level approach:** Completed with paginated Project/link discovery, current GraphQL create/link mutations, digest-confirmed apply, fresh-state validation, atomic action receipts, and simulated API tests.
- **Done when:** A user can start with only an organization and repository, explicitly select or create a Project, and reach an idempotent fully scaffolded state.

#### R04 - Reconcile complete Project view configuration

- **Status:** Not started; scheduled for Wave B
- **Importance:** High
- **Complexity:** Medium
- **Context:** Existing views are currently compared only by name and layout. A same-name Kanban or sprint view with the wrong filter, grouping, sort, or visible fields can be incorrectly treated as valid.
- **High-level approach:** Snapshot complete view configuration through the GitHub view APIs. Compare filters, grouping, sorting, and roadmap settings, then emit safe view-update actions or a precise fail-closed conflict.
- **Done when:** Incorrect same-name views are detected, repair plans converge, and a second scaffold plan is empty only when the full view contract matches.

#### R05 - Manage the iteration lifecycle

- **Status:** Not started; scheduled for Wave B
- **Importance:** High
- **Complexity:** Medium
- **Context:** The kit creates the Sprint field and can assign work to an existing iteration title, but it does not fully discover, select, create, extend, or roll over iterations.
- **High-level approach:** List current, completed, and upcoming iterations; select `@current` or calculate the next iteration deterministically; extend the schedule when required; validate requested sprint titles during planning rather than failing during apply.
- **Done when:** Sprint planning can select a valid current or next iteration, missing iterations are handled through a reviewed plan, and rollover/completed-iteration tests pass.

#### R06 - Evaluate the installed plugin and skill activation

- **Status:** Not started; scheduled for Wave C
- **Importance:** High
- **Complexity:** Medium
- **Context:** The plugin manifest and skills validate structurally, but the complete plugin has not been installed from a local marketplace and exercised through real Codex conversations.
- **High-level approach:** Install the checkout through a development marketplace and run a recorded evaluation set containing direct, indirect, follow-up, negative, and write-confirmation prompts. Repeat with GitHub MCP available and unavailable to confirm executor fallback.
- **Done when:** The intended skill activates consistently, unsupported requests do not activate it, bundled references resolve after installation, and authorization boundaries hold in end-to-end conversations.

#### R07 - Publish the repository, run Linux CI, and release `0.1.0`

- **Status:** In progress; local repository/package/release setup completed in Wave A, external publication remains Wave D
- **Importance:** High
- **Complexity:** Medium
- **Context:** Local Git history, package metadata, test/build/benchmark CI, and a tag-driven release workflow now exist and pass local audit. No GitHub remote has been created, and the Linux workflows have not executed.
- **High-level approach:** After Waves B/C pass, create `aegolius-labs/agentic-backlog-kit`, push the initial branch, enable required checks, verify Linux CI from a clean checkout, then tag and publish `0.1.0` with its documented artifacts and limitations.
- **Done when:** Windows and Linux checks are green from a clean checkout, branch protection is active, installation instructions work, and the tagged release contains documented artifacts and limitations.

#### R08 - Select a license and complete public-release documentation

- **Status:** Complete in Wave A
- **Importance:** High
- **Complexity:** Easy
- **Context:** The kit is source-available under PolyForm Noncommercial 1.0.0, with a separate paid license required for any for-profit operational use. Individuals may use it for genuinely noncommercial open-source work; making a project public does not convert commercial use into noncommercial use.
- **High-level approach:** Completed with consistent license/package metadata, commercial terms guidance, `SECURITY.md`, `SUPPORT.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, and release documentation. Final known limitations will be refreshed from Wave C results before release.
- **Done when:** Repository and package metadata agree, users understand permissions and support boundaries, and the release checklist contains no unresolved legal or documentation placeholders.

#### R09 - Measure and enforce token-efficiency targets

- **Status:** Complete in Wave A; rerun on the release candidate in Wave C
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

#### R13 - Decide whether to build a dedicated MCP server

- **Importance:** Conditional
- **Complexity:** Hard
- **Context:** The kit currently relies on the host GitHub MCP with CLI/API fallbacks. A custom server is useful only if live evaluation shows that the generic GitHub MCP cannot expose the required deterministic or compact operations.
- **High-level approach:** Use R02 and R06 results to identify missing operations, excessive tool calls, or poor result shapes. If justified, expose compact query, plan, validate, apply, and verify tools while keeping the local engine as the shared core.
- **Done when:** The decision is supported by evaluation evidence; if built, the server reduces calls/context and preserves the same plan/apply contract.

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

2. **Wave B - Project behavior completion**
   - Implement R04 view reconciliation and R05 iteration lifecycle after R03 establishes common Project and field identity helpers.
   - R04 and R05 can run concurrently only in isolated worktrees with agreed interfaces. In one working tree, do them sequentially because they edit the same GitHub, snapshot, and scaffold modules.
   - Prepare the disposable assets and evaluation scripts for R02 concurrently without executing the final test matrix yet.

3. **Wave C - Parallel release-candidate evaluation**
   - Run R02 live GitHub evaluation and R06 installed-plugin evaluation concurrently against the stable candidate.
   - Run Linux CI at the same time and rerun R09 measurements on the final behavior.
   - Failures return to the owning Wave A/B lane; do not patch production and evaluation branches independently.

4. **Wave D - Release closure**
   - Finalize R08 known limitations and permission documentation using evaluation results.
   - Complete R07 packaging, tag, and `0.1.0` release only after R02, R06, R09, Linux CI, and documentation gates pass.

5. **Wave E - Post-release parallel tracks**
   - R10 destructive/reverse reconciliation and R11 import/bulk ingestion may start concurrently after R01, but require isolated branches and a shared authority/conflict contract.
   - Begin R12 only after single-repository behavior and import/reconciliation policies stabilize.
   - Make the R13 MCP decision only after R02/R06 provide evidence; do not build a server preemptively.

### Critical path

```text
(R01 safety) + (R03 Project bootstrap -> R04 views + R05 iterations)
    -> R02 live GitHub evaluation + R06 installed-plugin evaluation
    -> R08 release documentation
    -> R07 tag and publish 0.1.0
```

R09 now has a recorded baseline and should run again on the release candidate. R07 local repository and CI setup are complete; external repository creation, Linux execution, and the final release remain on the critical path.

### Concurrency operating rule

The local Git repository now supports isolated worktree development, and Wave A validated that integration pattern. Continue assigning each concurrent lane its own branch/worktree. R04 and R05 still require an agreed Project identity/configuration contract before they run concurrently; R10 and R11 likewise require a shared authority/conflict contract.
