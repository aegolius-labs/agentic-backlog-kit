# Release checklist

This checklist records the completed documentation, validation, and publication
gates for `0.1.0`, released on 2026-09-04.

## Documentation and licensing

- [x] `pyproject.toml` and `.codex-plugin/plugin.json` agree on package name
  and version (`0.1.0`).
- [x] `LICENSE.md` states the PolyForm Noncommercial License 1.0.0 and links
  to the authoritative terms.
- [x] `COMMERCIAL.md` explains that all for-profit use requires a separate
  paid commercial agreement.
- [x] `SUPPORT.md`, `SECURITY.md`, and `CONTRIBUTING.md` state their public,
  commercial, and contribution boundaries.
- [x] README and architecture docs describe the supported transports,
  capability-complete MCP condition, label fallback, Project-view limits,
  eventual membership propagation, and additive/update-only scope.
- [x] Known limitations are linked to the Wave C validation and capability
  evidence; no legal or documentation placeholders remain.

## Local evidence

- [x] Windows and local Ubuntu WSL test/build/install/help checks pass; see
  [validation.md](validation.md).
- [x] Authenticated GitHub CLI and direct GraphQL/REST label-fallback lanes
  converged in Wave C with zero-action second plans.
- [x] Native-type scenarios stop before writes when `Story` is unavailable.
- [x] The installed generic GitHub MCP fails capability preflight before
  writes because its Project and repository lifecycle surface is incomplete.
- [x] Disposable-resource cleanup ran under a separate exact confirmation,
  stopped on its first repository-deletion failure, and did not affect the
  release or untouched API target.

## External release-owner gates

- [x] Publish the [canonical repository](https://github.com/aegolius-labs/agentic-backlog-kit)
  and verify hosted `ubuntu-latest` CI on the exact release commit.
- [x] Enable strict `test` branch protection with administrator enforcement and
  force-push/deletion disabled.
- [x] Create the `v0.1.0` tag and publish the validated source distribution and
  wheel in the [GitHub release](https://github.com/aegolius-labs/agentic-backlog-kit/releases/tag/v0.1.0).
- [x] Publish generated release notes; this checklist and the complete release
  documentation are included in the tagged source archive.
