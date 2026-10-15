# Compatibility policy and 1.0 criteria

This page states what a release of the kit may change, and what must be true
before a release is called 1.0. It answers S-R33-2 and production readiness
gate 11.

## Versions

Versions are computed by the organization's release automation from
Conventional Commit history, never chosen by hand: `fix:` cuts a patch, `feat:`
a minor, and a breaking-change footer (`!` or `BREAKING CHANGE:`) a major.
Choosing the commit type is therefore how a change declares its compatibility,
and this policy says which type a change must carry.

## What the promise covers

These are the kit's public formats. A user keeps them on disk or in GitHub
issue bodies, so a change to any of them can strand existing state.

| Surface | Where it lives | Current version |
| --- | --- | --- |
| Manifest | `.agentic-backlog/manifest.json`, [schema](../schemas/manifest.schema.json) | `schema_version` 2; 1 is still read |
| Issue marker | hidden comment in each managed issue body: `<!-- agentic-backlog-kit:id=ID;schema=1[;guid=GUID] -->` | `schema=1` |
| Written-content marker | `<!-- agentic-backlog-kit:written=v1;title=...;body=... -->` | `v1` |
| Plans | JSON written by `init-plan`, `scaffold-plan`, `sync-plan` and peers, bound by their `digest` | unversioned (see below) |
| Receipts | JSON written by every apply | unversioned (see below) |
| Observed-state evidence | `abk observe`, [schema](../schemas/observed-state.schema.json) | `contract_version` 1 |
| Command line | the `abk` subcommands and their documented flags | - |
| Skills | the six `backlog-*` skill names and what each is for | - |

Not covered: anything under `.agentic-backlog/cache/`, internal Python modules
and functions, the wording of human-readable output, benchmark and evaluation
harnesses, and token budgets.

## Rules

**Patch and minor releases never break a covered surface.** In particular:

- The kit keeps reading every manifest `schema_version` it has ever written.
  A new manifest version is introduced only together with an in-place upgrade
  on read, as version 1 to 2 was.
- The kit keeps recognizing every issue marker it has ever written. New marker
  keys are appended after the existing ones, so an older reader that takes the
  id up to the first `;` still works. The marker's `schema` number changes only
  in a major release.
- A plan is valid only for the kit version that wrote it, because apply
  rebuilds and re-verifies it against fresh state before writing. Plans are
  therefore not a storage format: a minor release may refuse a plan written by
  an older version, and must do so by failing closed before any write, never by
  applying it differently.
- Receipts are an audit record. A minor release may add receipt fields but
  never removes or renames one, or changes what an existing field means.
- The observed-state contract follows the same rule as receipts within one
  `contract_version`. A change that removes or redefines a field raises
  `contract_version`, and the kit then emits the old version for at least one
  further minor release on request.
- A subcommand, flag or skill is removed or renamed only in a major release.
  A minor release may add them, and may deprecate one with a warning first.
- The supported Python range (`requires-python`) only widens in a minor
  release. Dropping a Python version that has reached its upstream end of life
  is the one exception, and it is announced in the release notes.

**A major release may break a covered surface**, and then must ship with a
migration path: an upgrade command or upgrade-on-read for stored state, and a
changelog entry that names every surface it breaks.

**Safety never counts as a break.** A release that makes the kit refuse an
input it used to accept, because accepting it could write the wrong thing to
GitHub, is a `fix:`. Failing closed is the contract.

### Before 1.0

While the version is 0.x, a minor release may break a covered surface, but
only with the same migration path and changelog entry a major release needs.

Such a change is committed as `feat:` and must **not** carry `!` or a
`BREAKING CHANGE:` footer. The release automation
(`mathieudutour/github-tag-action`, through the organization's
`compute-release` workflow) turns any breaking marker into a major bump, and a
major bump of 0.18.x is 1.0.0. A breaking marker on a 0.x line would therefore
cut 1.0 by accident. The break is named in the PR body and the changelog
instead.

## 1.0 criteria

1.0 is a promise to teams outside Aegolius Labs. It is cut when every
[production readiness gate](production-readiness-2026-09-24.md#gates) is met:

| Gate | Met by |
| --- | --- |
| 1-3, 5, 6, 9, 10, 13 | Met; see the readiness report and R28, R29, R32, R33, R35 |
| 4 - Closes the work lifecycle | R10, all four stories, with its post-merge sync converged |
| 7 - Installs without cloning, with a quickstart | S-R30-2: the [quickstart](quickstart.md) followed end to end on a fresh fixture, with evidence in [validation.md](validation.md) |
| 8 - Agent behavior verified on the current release | S-R31-1 and S-R31-2: the installed-plugin corpus run in both Codex and Claude Code against one release |
| 11 - Stability promise | This policy |
| 12 - Proven outside Aegolius Labs | R34: one outside team has run the quickstart on its own repository and relied on the kit for at least one sprint |

The 1.0 release is cut by a commit carrying a `BREAKING CHANGE:` footer that
names this policy as the change, which also moves the package classifier from
Alpha to Production/Stable.
