# Changelog

All notable changes to this project will be documented here.

The format follows Keep a Changelog, and releases use semantic versioning.

## [Unreleased]

### Added

- Capability preflight for execution routes (R13). Every action kind declares
  the capabilities it requires and every transport declares what it provides,
  so sync, scaffold, iteration, bootstrap and import all refuse before their
  first write when the selected route cannot finish the plan, naming each
  missing capability instead of failing partway through.
- `abk capabilities` reports what the selected route can and cannot do without
  planning anything.
- `abk gantt` projects the backlog onto a timeline and renders it as a Mermaid
  Gantt chart, in Markdown, bare Mermaid, or JSON. Durations come from effort
  points times one declared factor and order from the dependency graph the
  manifest already proves acyclic, so the projection is deterministic and can be
  regenerated and diffed rather than maintained by hand. Every chart states its
  basis and that it is a projection rather than an estimate. Mermaid renders
  natively on GitHub, so this adds no runtime dependency.
  `docs/roadmap-gantt.md` is the generated projection of this repository's own
  backlog, and a test fails when it no longer matches the manifest.
- `abk next --explain N` reports the higher-ranked items it passed over, each
  with the reason: unrefined, waiting on a named dependency, explicitly blocked,
  or a container whose children carry the work. Selection previously discarded
  all of those silently, so an answer that looked wrong could not be audited by
  anyone who had not read the engine.
- `abk import-reconcile --infer-relationships` recovers the sub-issue parent and
  `blocked by` dependencies GitHub records for each stranded marker, instead of
  recovering it flat. Recovering flat reproduced exactly the divergence
  adoption's relationship inference removes: the item claimed no structure while
  GitHub still held one, and additive synchronization never reconciles that.
  Recovery resolves a relationship against the ids it is about to write as well
  as the manifest, because one stranded issue can be the parent of another.
- A `backlog-adopt` skill, so adoption is reachable from the installed plugin
  and not only from the CLI. Previously `skills/` covered initialization,
  ingestion, prioritization, sprint planning and synchronization, and said
  nothing about adoption, so an agent working through the plugin could manage a
  backlog it had created but could not take on a repository that already had
  issues. Four activation cases cover it.
- `abk import-plan --infer-relationships` proposes the sub-issue parent and
  `blocked_by` dependencies GitHub already records, instead of adopting every
  issue flat. It is opt-in because it costs two extra reads per unmanaged
  issue. A relationship the manifest cannot express — a parent that is not
  exactly one hierarchy level above, a reference to an issue outside the
  adoption, or a dependency that would close a cycle — is withheld and reported
  under `withheld_relationships` rather than forced.

### Fixed

- The CLI route reported a 403, 429 or 500 as exit code 1, so the hints that
  explain a failure fired on the direct API route and never on `gh`. The
  reported status is now taken as the status, except that a 404 is mapped only
  for the exact parent-absence case, because that endpoint also answers 404
  when the issue itself is absent.

### Changed

- The direct GraphQL/REST transport is documented and typed as a peer of the
  CLI route rather than a fallback for hosts without `gh`.

### Fixed

- A release run with no version tag behind it now fails instead of reporting
  success and publishing nothing (R14-F7). The calculator derives the next
  version from commits since the last release tag, so with no tag it produces
  none, which every later job read as a legitimate no-bump. A `baseline-guard`
  job runs on exactly the runs preflight does not and fails when a no-bump has
  no baseline, naming how to create one. It is read-only and never creates a
  tag; the release contract rejects any change that would weaken that.

### Added

- Adoption of issues a repository already has (R11). `import-plan` previews
  which unmanaged issues would become backlog items and writes nothing;
  `import-apply` adopts exactly the reviewed plan, prepending the kit's marker
  to each issue body without removing anything already written, and records the
  item in the manifest so synchronization takes over without creating a
  duplicate. `--include` and `--limit` bound what is adopted; everything else
  is reported with its reason.
- `import-reconcile` records marked issues the manifest lost, touching nothing
  on GitHub. Adoption marks GitHub before the manifest records the item, so an
  interruption between those steps strands the issue; `import-plan` now reports
  these as `orphans`.

### Fixed

- Import saved the manifest without pinning the version it had read.

### Added

- A failed apply now records a `hint` naming the likely cause alongside the
  failing action (R22). An unavailable native issue type names the type, the
  remedy, and the label that would be used instead; permission, absence and
  rate-limit failures say what to do next. Unknown causes stay silent rather
  than guessing.
- A scaffold plan reports `converges_in_one_apply` and, when a view is being
  created, a `follow_up` explaining that GitHub cannot configure a view at
  creation time and a second plan is needed (R23). The completed receipt
  carries the same note, so a completed apply never implies a converged target.

### Changed

- The CLI prints a structured JSON error on stderr and exits non-zero instead
  of raising a traceback, including the failing action and hint from the
  receipt when one was written.

### Added

- Sprint planning preserves commitments (R16, carryover policy D2/A). Work
  already committed to the target sprint is retained, counted once against
  capacity, and keeps its status instead of being re-selected. Work committed
  to another sprint is withheld from automatic selection however highly it
  ranks, and moves only when named with `sprint-plan --carryover ID`.
- A plan reports `retained`, `retained_effort`, `overage`,
  `carryover_available` and `carryover_selected`. Commitments beyond capacity
  surface as an explicit overage rather than silently dropping work.

### Changed

- `--skipped-limit` now projects the retained and carryover lists as well as
  the skipped one, each with a count and truncation marker, which keeps a
  10,000-item sprint plan at roughly 8 KB instead of 555 KB.
- `sprint-plan` without a target sprint ignores sprint assignment and ranks the
  whole backlog as before: commitment is relative to a target, so with no
  target there is nothing to protect and no elsewhere to withhold from.

## [0.2.0] - 2026-09-19

### Added

- GitHub now owns `Status` and the iteration field for work it already tracks
  (R15, policy D1). Ordinary synchronization no longer rewrites them, so a card
  someone moves on the board survives the next sync. A new item still receives
  the manifest's operational defaults the first time it is projected.
- `sync-plan --transition ID=STATUS` and `--transition-sprint ID=SPRINT` move
  operational state deliberately. A transition is recorded in the plan, folded
  into its digest, and bound to the value observed at planning time, so a
  concurrent change aborts the apply before any write.
- `prioritize`, `next` and `sprint-plan` accept `--operational-snapshot` to rank
  against fresh GitHub state, report whether they used `github` or
  `local-intent` state, and expose differences with
  `--report-operational-drift`.
- `scripts/set_version.py` stamps the computed release version across every
  declaration and promotes the changelog's Unreleased section, so the
  organization's computed version reaches the package without a manual bump
  (R14-F8).

### Fixed

- Completed work is released before unfinished work when ordering the backlog.
  Scoring it zero had made it sort last, which held back everything depending
  on it: the next executable item could be a lower-value one while the
  genuinely next work sank out of the ranked head.
- `select_next` returns the highest-scoring executable item rather than the
  first one dependency order happens to reach.
- A sync plan is scored against the state it intends to leave behind, so a
  transition and its derived `Priority` settle in one apply.

### Documentation

- Recorded the completed Wave D publication, hosted CI, branch protection,
  published artifact digests, clean-checkout verification, and fail-closed
  partial disposal of the Wave C evaluation resources.

### Changed

- Replaced the repository-specific tag publisher with the versioned Aegolius
  Labs reusable Conventional Release workflow, guarded by a dry-run version
  computation, package/plugin preflight, and post-upload asset verification.

## [0.1.1] - 2026-09-19

### Fixed

- Resolved dependency graphs iteratively. Prioritization previously raised
  `RecursionError` from roughly 500 chained items and validation from roughly
  1,200; 10,000-node chains now resolve, deep cycles are still detected, and
  cycle diagnostics are bounded to a fixed length.
- Zeroed the final score of completed work. The dependency boost still
  propagated from dependents into a completed item's final score, so finished
  work could outrank and inflate the work that remained.
- Recovered the HTTP 422 that `gh api` reports only as exit code 1, for issue
  create and update. In `native_or_label` mode an unavailable native issue type
  is meant to fall back to a type label, and that fallback could never fire on
  the CLI route: the same manifest converged through the direct API and failed
  mid-apply through `gh`.

### Changed

- Re-cut the roadmap into release lines, each counted against its own
  membership, and recorded the first-use findings from managing this
  repository's own backlog through the kit.
- Synchronized the package, plugin, and marketplace version declarations so a
  release-bearing merge matches the computed semantic version.

## [0.1.0] - 2026-09-04

### Changed

- Finalized release-candidate transport support and known-limitations
  documentation from the Wave C evidence: authenticated GitHub CLI and direct
  GraphQL/REST are supported peer routes, capability-complete MCP is
  conditional, and incomplete generic MCP surfaces fail closed.
- Documented the `type:*` label fallback when native `Story` is unavailable,
  additive/update-only mutation scope, Project-view update boundaries,
  eventual Project-membership propagation, and the noncommercial/paid-
  commercial licensing boundary.
- Modernized package license metadata to the SPDX PolyForm identifier and
  include both legal notice files in built distributions.

### Added

- Fresh-state-bound sync, scaffold, and bootstrap plans with per-action preconditions and atomic partial-execution receipts.
- Deterministic organization Project discovery, exact selection, creation, repository linking, and first-run manifest bootstrap.
- Repeatable 100/1,000/10,000-item payload benchmarks with CI-enforced byte budgets and bounded sprint-plan projections.
- Local Git, package build/smoke-test, and tag-driven GitHub release scaffolding.
- PolyForm Noncommercial licensing, paid-commercial guidance, and public support, security, contribution, and release documentation.
- Complete Project view snapshots and semantic reconciliation for layout, filters, ordered visible fields, grouping, and sorting, with safe updates or precise fail-closed conflicts.
- Deterministic active/completed iteration discovery, exact and alias resolution, safe rolling schedule extension, digest-confirmed apply receipts, and refreshed identity verification.
- An offline disposable-GitHub evaluation package covering GitHub CLI, API, and MCP backends in native-type and label-fallback modes, including evidence verification and separately authorized cleanup.
- A bounded installed-plugin trace runner with fail-closed multi-turn continuation, safe path canonicalization/redaction, validated local-ingestion mutation proof, and durable Wave C representative evidence.
- Safe initialization planning for GitHub iteration fields that exist with an empty server configuration.
- Direct-API compatibility for GitHub's zero-duration sentinel on a null-start, empty iteration field, while preserving positive-duration validation for initialized schedules.
- GitHub CLI snapshot compatibility for its explicit root-issue parent-absence 404 diagnostic, with unrelated CLI failures remaining fail-closed.
- Five focused Codex backlog skills.
- Compact manifest validation and deterministic priority scoring.
- Dependency-safe sprint planning.
- GitHub Issue, Project, hierarchy, dependency, and field reconciliation.
- Digest-confirmed scaffold and synchronization plans.

[Unreleased]: https://github.com/aegolius-labs/agentic-backlog-kit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/aegolius-labs/agentic-backlog-kit/releases/tag/v0.1.0
