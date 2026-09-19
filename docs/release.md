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

The shared workflows merged in [organization PR #4](https://github.com/aegolius-labs/.github/pull/4)
at `9f323e5ef1266f90f6b10c3aa3a595a0f3542ab9`; the initial caller merged in
[ABK PR #1](https://github.com/aegolius-labs/agentic-backlog-kit/pull/1).
Its first main release run failed to load the pre-merge shared pin after squash
merge and automatic branch deletion. The corrected caller pins both workflows
and publisher source to the merged shared commit. CI verifies that the pin is in
shared main history and that workflow contents match the reviewed fixtures.
The corrected caller merged in ABK PR #2. Hosted no-bump and Plan L immutable
publication passed; missing-baseline handling and hosted failure recovery remain.

### Versions are stamped, never predicted

Nothing in the tree needs to declare the next version. `set_version.py` writes
the computed version into `pyproject.toml`, both plugin manifests, the
marketplace entry and `__init__.py`, and promotes the changelog's
`## [Unreleased]` section into that version's entry. Preflight runs it against
the candidate checkout before building, so the distributions carry the computed
version and `release_check.py` compares like with like.

Nothing is committed or pushed. The tag remains the record of what a version
means, and the tree's declared version is simply the last one stamped there.
Contributors write changelog entries under `## [Unreleased]` without knowing
which release will carry them.

This closes R14-F8. Before it, a release-bearing merge computed a tag the tree
could not match, and preflight refused - correctly, and twice, because the
manual bump is exactly the kind of step people forget.

A stable version baseline is currently required: untagged feature history can
silently compute no release (R14-F7). A clear no-write prerequisite guard is
planned. Do not treat a successful untagged no-op as first-release support or
create a baseline automatically. Plan L used an explicitly approved fixture tag.

1. `compute-release.yml` runs with contents read permission, computes the
   Conventional Commit version without tagging or bootstrap writes, and binds
   candidate SHA and tag-state fingerprint. No-bump skips remaining jobs.
2. ABK checks out the exact candidate, runs tests/help/budgets, stamps the
   computed version with `set_version.py`, then builds and smoke-tests the
   package and uses `release_check.py` to enforce aligned
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

Plan G completed draft publication. The user then authorized both merges and the
existing organization-admin review bypass for shared PR #4 only. No protection
settings changed. Activation Plan H recorded both merges and stopped on the first
ABK release-load failure; recovery uses a new plan, never replays completed merges.

After squash merges, use the accepted shared main commit rather than the old PR
head. Raw files can remain readable after their branch disappears while Actions
refuses the reusable workflow reference. Verify ancestry, contents, and hosted
behavior before closing activation.

[Remaining rollout checklist](release-checklist.md#post-010-automation---r14-remediation-gates)
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

## Hosted release checkpoint (2026-09-13)

On 2026-09-13, approved Plan L completed all five actions. The unchanged fixture
main `1bba7e6790c410631d562227379b269c5dade6f7`, with an explicitly approved
`v0.0.0` baseline at `55a6dc3e9616a0e8cd446cf84c78d7fa48328428`, passed
[hosted compute, preflight and publication](https://github.com/aegolius-labs/abk-release-eval-20260908/actions/runs/34781149178). Its
[immutable v0.1.0 release](https://github.com/aegolius-labs/abk-release-eval-20260908/releases/tag/v0.1.0) contains exactly the preflighted wheel and
source archive. Downloaded names, sizes and SHA-256 hashes matched; package
metadata, isolated wheel installation and `abk --help` passed. The publisher
receipt records draft asset verification before publication and final verification.
Production main commits, protections, immutability settings and release inventories
were unchanged. The fixture is retained; no cleanup occurred.

R14 remains ongoing: untagged release-bearing history silently analyzed zero
commits before baseline setup (R14-F7). Document and enforce the baseline
prerequisite without automatic tag creation, and separately prove hosted recovery
after draft creation and partial upload. Local recovery tests alone do not close
that gate. R15 is the next product implementation item; D1 and carryover policy A
are approved. This documentation refresh is local and has not been published.
