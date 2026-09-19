# Changelog

All notable changes to this project will be documented here.

The format follows Keep a Changelog, and releases use semantic versioning.

## [Unreleased]

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
