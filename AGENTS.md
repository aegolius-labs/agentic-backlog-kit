# Repository guidance

## Purpose

This repository packages Codex skills and a deterministic Python engine for GitHub Issues and Projects backlog management.

## Invariants

- GitHub is the operational system of record; the tracked manifest is compact desired configuration and managed item intent.
- External writes must follow plan, validate, explicit digest confirmation, apply, and post-apply verification. The organization-managed release workflow is the explicit exception: a release-bearing Conventional Commit merged to protected `main` authorizes its preflighted semantic tag, GitHub Release, and validated artifact upload.
- Do not add issue deletion, Project item deletion, or automatic issue closure without an explicit product decision and tests.
- Keep the runtime dependency-free unless a dependency provides a concrete benefit that cannot be achieved safely with the standard library.
- Preserve stable item IDs and the hidden GitHub issue-body marker.
- Reject hierarchy and dependency cycles before planning any mutation.

## Verification

Run:

```powershell
python -c "import sys, unittest; sys.path.insert(0, 'src'); suite=unittest.defaultTestLoader.discover('tests'); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())"
python scripts/backlog.py --help
```

Validate every changed skill with the bundled skill validator and validate the plugin manifest with the bundled plugin validator before handoff.
