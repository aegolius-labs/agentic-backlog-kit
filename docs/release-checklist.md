# Release checklist

This checklist records the documentation and local validation gates for the
`0.1.0` release candidate. Publication, hosted CI, branch protection, and tag
creation remain external release-owner actions.

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
- [x] Disposable-resource cleanup remains separately confirmed and is not
  part of normal backlog synchronization.

## External release-owner gates

- [ ] Publish the canonical repository and verify hosted `ubuntu-latest` CI.
- [ ] Enable and verify required branch protection checks.
- [ ] Create the `v0.1.0` tag and publish the source distribution and wheel.
- [ ] Attach the final release notes and this checklist to the published
  release.
