# Release and publication plan

This is the R07 publication runbook for the first public release. It is
deliberately limited to the canonical repository and the Python distribution;
there is no PyPI publishing workflow.

## Execution result

The exact publication plan, digest
`adfa9a0354010f9b3a4a289acfbe305c469b9c2a71adee5bef00dc5d255db130`,
was confirmed and completed on 2026-09-04. Public repository
`aegolius-labs/agentic-backlog-kit`, protected branch `main`, hosted Linux CI,
annotated tag `v0.1.0`, the generated GitHub release, both distribution assets,
and a clean public-tag checkout were verified against commit `6a14b70`.
Authoritative run URLs and published artifact digests are recorded in
[validation.md](validation.md).

Disposable Wave C resource cleanup used a separate destructive plan. It
stopped safely after deleting Project #4 when the following repository deletion
failed; no retry or API-target action occurred. Remaining cleanup requires a
new plan and is not part of the successful R07 release result.

## Ongoing organization-managed releases

R14's corrected implementation is local and validated, pending draft publication
and hosted evidence. ABK pins both new organization workflows and the publisher
source checkout to `194c01743a7a41d75c41e1434d8ca02b3702a586`. This SHA is a local
candidate, not an already published shared version. Publish the shared revision
before pushing the ABK caller; its CI verifies the pinned public workflow files.

1. `compute-release.yml` runs with contents read permission, computes the
   Conventional Commit version without tagging or bootstrap writes, and binds
   candidate SHA and tag-state fingerprint. No-bump skips remaining jobs.
2. ABK checks out the exact candidate, runs tests/help/budgets, builds and
   smoke-tests the package, and uses `release_check.py` to enforce aligned
   package/runtime/plugin/changelog metadata. `release_inventory.py` binds the
   exact two files, sizes/hashes, tag, SHA, tag state, and notes. The upload's
   artifact ID and inventory hash become publisher inputs.
3. `publish-release-assets.yml` downloads only that artifact from this run,
   validates every input and file, and rechecks main/tag state before writes.
   Organization-owned code creates a tag and marked draft, attaches missing
   matching assets, verifies downloaded bytes, and publishes last. Final
   verification requires the exact assets, commit, and immutable release.
4. The released output becomes true only after verified publication. The
   30-day receipt records completed steps, release identity, and failure state.

Existing `conventional-release.yml` callers and aio-agentic-sdlc's separate PyPI
path are unchanged. ABK neither publishes to PyPI nor relies on a secondary
GITHUB_TOKEN-triggered workflow. Runtime dependencies remain unchanged. YAML
contract validation uses pinned PyYAML only in CI/audit tooling; the complete
unit suite and packaged engine remain dependency-free.

Keep bundles and receipts for 30 days. Recover by rerunning only the failed
publisher job with its original bundle and inputs. A matching draft resumes;
identical published state is a verified no-op. Changed assets, identities, tags,
or unrelated releases stop for reviewed remediation. Never clobber/delete assets
or rewrite tags. After bundle expiry, rebuilding is not proof of byte identity.

Before rollout, separately read the immutability setting with the release owner's
administration-read access. It is currently enabled and owner-enforced in both
repositories. GITHUB_TOKEN cannot read that admin setting; the publisher checks
`immutable: true` after publication and preserves state on a failed check. Do not
change the setting while publishing.

Replacement Plan G publishes the exact shared and ABK branches and creates draft
PRs only. It does not merge, tag, release, or clean up resources. The shared
repository requires one approval, code-owner review, resolved conversations,
squash merge, and CodeQL policy checks. Do not bypass those rules. Keep the pinned
shared branch while reviewing; if integration changes its source, re-pin and
revalidate ABK against the resulting exact commit before activation.

[Pending rollout checklist](release-checklist.md#post-010-automation---r14-remediation-gates)
and [local validation evidence](validation.md#r14-corrective-implementation-local-evidence)
separate local correctness from hosted proof. Historical Plan F is superseded.

## Historical `0.1.0` audit snapshot

The 2026-09-04 audit found:

- The audit baseline worktree was clean on `codex/wave-d-r07-audit` at
  `444a71d4d8596987212cf304de8b3e5207f6ae36` and had no Git remotes. The
  R07-only preflight/docs changes in this worktree must be included in the
  final candidate SHA before publication.
- The authenticated GitHub account is `MustacheMushroom`, with active admin
  membership in `aegolius-labs` and `repo`, `workflow`, `project`, and
  `read:org` scopes. The target repository
  `aegolius-labs/agentic-backlog-kit` is absent (REST 404 and GraphQL not
  found), so the name is currently available to this account.
- Public visibility is the intended audience. The canonical owner/name and
  public URL are already repeated in the plugin manifest, package metadata,
  changelog links, and user documentation. No credential-looking tracked
  paths or high-risk token/private-key literals were found.
- `.github/workflows/test.yml` runs the complete suite, CLI help, package
  build/install smoke test, and benchmark budget check on `ubuntu-latest`
  for pushes and pull requests. `.github/workflows/release.yml` is triggered
  only by `v*` tags, builds the wheel and sdist, verifies licensing files,
  validates the tag and artifacts, and creates a GitHub release with those
  two assets.
- `pyproject.toml`, `.codex-plugin/plugin.json`, and
  `src/agentic_backlog_kit/__init__.py` all declare `0.1.0`; `CHANGELOG.md`
  contains the corresponding entry. A clean local build produced exactly
  `agentic_backlog_kit-0.1.0-py3-none-any.whl` and
  `agentic_backlog_kit-0.1.0.tar.gz`, and the release preflight validated
  their metadata, entry point, source contents, names, sizes, and SHA-256
  digests.
- Branch protection and hosted checks cannot be observed until the target
  repository exists. The existing `aegolius-labs/aio-agentic-sdlc` `main`
  branch is not protected; it is reference-only and does not satisfy R07.

The Python sdist and wheel contain the deterministic runtime. The plugin
skills and `.codex-plugin/plugin.json` are delivered by the public repository
or its tag archive, not by the wheel. This boundary is intentional and avoids
making a Python installation look like a complete plugin installation.

## Historical initial publication plan

Run every step against the exact target `aegolius-labs/agentic-backlog-kit`,
default branch `main`, and release tag `v0.1.0`. Stop when any precondition or
verification fails.

1. **Freeze and validate the candidate locally.** On the final candidate
   commit, update the `0.1.0` changelog heading from `Unreleased` to the
   release date, then run the complete test, CLI, benchmark, build/install,
   and `python scripts/release_check.py --tag v0.1.0 --dist dist` checks from
   a clean checkout. Record the candidate commit and both artifact digests.
   This is local-only work covered by “Proceed with Wave D”.
2. **Confirm identity and name availability.** Read `gh auth status`, the
   `aegolius-labs` membership, and the exact target repository. Require an
   active account with organization repository-create/admin rights and a
   not-found target. These are read-only checks covered by “Proceed with Wave
   D”; re-authentication, if needed, is a user action.
3. **Create the canonical public repository.** Create exactly
   `aegolius-labs/agentic-backlog-kit` with public visibility, Issues enabled,
   and default branch `main`, without an auto-generated README or license
   that could diverge from the candidate. Public creation is a material
   external write and requires an exact confirmation even though Wave D has
   been approved; the repository invariants require a reviewed plan and
   explicit digest confirmation before applying it.
4. **Push the reviewed candidate.** Add only the canonical `origin`, push the
   final candidate commit to `main`, and do not push a tag yet. Verify that
   `origin/main` resolves to the recorded candidate SHA and that the public
   tree contains the expected plugin and licensing files. Adding the remote
   and pushing are external writes requiring exact confirmation.
5. **Observe hosted CI before protection or release.** Wait for the `test`
   workflow on that exact `main` SHA. Require a completed `success` conclusion
   for the complete suite, package smoke test, and benchmark check. A failed,
   cancelled, or stale run blocks the next step; fix the candidate locally,
   revalidate, and push a newly reviewed SHA rather than bypassing CI.
6. **Apply branch protection to `main`.** After the green run, configure the
   target branch with strict required status checks containing exactly the
   `test` job, administrator enforcement, force-push disabled, and branch
   deletion disabled. Decide explicitly whether pull-request review rules are
   required; do not silently invent a review count. Read the protection
   response back and verify all selected settings. This external write needs
   an exact confirmation and a digest of the proposed settings.
7. **Publish the reviewed tag.** Re-run the local release preflight against
   the same candidate and exact tag `v0.1.0`, create the tag at the verified
   SHA, and push only `v0.1.0`. The tag push is an external write and starts
   the release workflow, so it requires an exact confirmation. Do not push a
   wildcard or a tag whose version differs from package metadata.
8. **Verify the generated GitHub release.** The tag workflow must finish
   successfully. Verify release `v0.1.0` is not a draft or prerelease, points
   to the intended tag, and contains exactly the wheel and sdist named above.
   Download those assets to a disposable directory, run the release preflight
   against them, record their SHA-256 digests, install the wheel with
   dependencies disabled, and run `abk --help`. Build-container timestamps can
   make archive digests differ from a local build, so digest equality is not a
   release requirement unless reproducible-build controls were explicitly
   applied. No PyPI upload is implied or authorized by this plan.
9. **Verify the public clean-checkout path.** From a fresh clone of
   `https://github.com/aegolius-labs/agentic-backlog-kit` at `v0.1.0`, rerun
   the documented local checks and confirm the plugin manifest resolves
   `./skills/` and the canonical links work. Record the CI run URL, protection
   response, tag SHA, release URL, asset names/digests, and any known
   limitations before declaring R07 complete.

## Recovery boundaries

- Before repository creation, a failed precondition leaves no external state.
  If the name is taken or visibility is uncertain, stop; do not select a
  similarly named repository.
- After public creation, do not delete the repository or rewrite its history
  as an automatic rollback. If publication is paused, preserve the exact
  state and obtain a separate confirmation before changing visibility or
  deleting anything.
- A failed hosted check blocks protection/tagging. Correct the candidate,
  rebuild, and push a new reviewed commit; never release a stale green SHA.
- If protection settings are wrong, read the applied settings, prepare a
  corrected settings digest, and update them after confirmation. Do not
  disable protection merely to force a push.
- If a tag or release is wrong, stop further publication and preserve the
  evidence. Prefer a corrected follow-up release after review; deleting a
  tag, release, or asset, or force-pushing a replacement, is a separate
  destructive decision and is not part of R07 approval.

## Authority summary

“Proceed with Wave D” covers read-only GitHub probes, local validation/builds,
and preparation or review of the exact publication plan. It does not by
itself satisfy the repository invariant requiring an explicit digest
confirmation for external writes. Exact confirmation is required for public
repository creation, pushing `main`, applying branch protection, pushing
`v0.1.0`, creating or editing the GitHub release, changing visibility, and any
deletion, tag rewrite, force-push, or asset replacement. None of those
external mutations were performed during this audit.
