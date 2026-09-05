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

## Post-`0.1.0` automation - R14 remediation gates

The corrected caller and shared implementation pass local contract/failure tests
and workflow syntax validation. Hosted and external acceptance gates remain open.
See [the remediation proposal](remediation-plan.md#r14-repair-shared-release-integration-f1f2).

- [x] Implement a separate read-only compute workflow and draft-first shared publisher.
- [x] Pass effective-permission, exact-artifact, drift, partial-failure, and no-op recovery tests locally.
- [x] Pin caller/source to the same full shared commit; verify actual local YAML contracts and actionlint syntax.
- [x] Independently read both repositories' enabled, owner-enforced immutability settings.
- [ ] Publish a validated organization interface for read-only version computation
  and asset-aware draft publication; pin the ABK caller to that version.
- [ ] Verify effective permissions and no writes for no-bump/compute-only cases,
  including an untagged fixture without bootstrap mutation.
- [ ] Bind tests, versions, candidate SHA/tag, and exact wheel/sdist hashes before
  the first release write; reject mismatch or drift.
- [ ] Create the draft, attach and verify both assets, then publish and verify
  immutability and the exact final inventory.
- [ ] Prove recovery after draft/partial upload failure without replacement of
  unrelated, mismatched, or already published state.
- [ ] Preserve no-bump behavior and organization ownership of releases; require
  no secondary event-triggered workflow or PyPI publication.
- [ ] Record hosted no-bump and authorized immutable-release run evidence before
  protected-branch delivery is marked complete.

## Corrective product delivery

- [ ] R15: GitHub operational authority and explicit transitions verified.
- [ ] R16: retained capacity/status and reviewed carryover verified.
- [ ] R17: deep graph and controlled-cycle regressions pass.
- [ ] R18: completed final scores are zero across dependency cases.
- [ ] R19: public main status matches verified delivery after publication.

R20 disposable cleanup remains separately confirmed and is not a product gate.
