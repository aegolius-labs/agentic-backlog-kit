# Repository guidance

## Purpose

This repository packages Codex skills and a deterministic Python engine for GitHub Issues and Projects backlog management.

## Invariants

- GitHub is the operational system of record; the tracked manifest is compact desired configuration and managed item intent.
- External writes must follow plan, validate, explicit digest confirmation, apply, and post-apply verification. The organization-managed release workflow is the explicit exception: a release-bearing Conventional Commit merged to protected `main` authorizes its preflighted semantic tag, GitHub Release, and validated artifact upload. A second, narrower exception was decided on 2026-09-24: a sync plan consisting solely of Priority field updates is pre-authorized. It is still planned against fresh state, verified after apply, and receipted; S-R10-4 makes the engine enforce the boundary, and until then the plan must be read and confirmed to contain nothing else.
- Do not add issue deletion, Project item deletion, or automatic issue closure without an explicit product decision and tests. The 2026-09-24 decision (R10) permits proposing a parent's closure once every child is closed, through the ordinary confirmed plan; it never permits closing an issue because the manifest no longer lists it.
- Keep the runtime dependency-free unless a dependency provides a concrete benefit that cannot be achieved safely with the standard library.
- Preserve stable item IDs and the hidden GitHub issue-body marker.
- Reject hierarchy and dependency cycles before planning any mutation.

## Organization authority model

- The normative statement of which Aegolius Labs repository owns which kind of
  truth is `doc/authority-model.md` in `aegolius-labs/aio-agentic-sdlc`.
- Composed with that framework, this kit is a one-way projection of work onto
  GitHub for human and team visibility. It does not decide what should be built.
- Used standalone, GitHub is the system of record outright. Standalone use is a
  supported configuration, not a degraded mode.
- Downstream state flows back as evidence, never as intent.

## Supported hosts

- `skills/` is the single source of truth for behavior. Do not fork skill content
  per host.
- Each host gets a thin manifest: `.codex-plugin/plugin.json` for Codex,
  `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` for Claude
  Code. `tests/test_host_manifest_parity.py` enforces that they agree.
- Claude Code specifics are in `CLAUDE.md`, which imports this file.

## Verification

Run:

```powershell
python -c "import sys, unittest; sys.path.insert(0, 'src'); suite=unittest.defaultTestLoader.discover('tests'); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())"
python scripts/backlog.py --help
```

Validate every changed skill with the bundled skill validator and validate the plugin manifest with the bundled plugin validator before handoff.

For Claude Code, the bundled validator is:

```powershell
claude plugin validate .claude-plugin/plugin.json
claude plugin validate .claude-plugin/marketplace.json --strict
claude plugin validate skills --strict
```

The plugin manifest is validated without `--strict` because it emits one known,
accepted warning:

> `root: CLAUDE.md at the plugin root is not loaded as project context.`

That is correct and expected. `CLAUDE.md` here is guidance for contributors
working *in* this repository, not context shipped to plugin consumers. Everything
a consumer needs lives in `skills/`. Do not silence the warning by moving
repository guidance into a skill. The marketplace manifest and `skills/` must
keep passing `--strict`.
