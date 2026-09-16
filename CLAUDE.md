# Agentic Backlog Kit — Claude Code guidance

@AGENTS.md

The instructions above are the canonical repository guidance and apply in full.
This file adds only what differs when the host is Claude Code.

## Organization authority model

This repository is one of three related Aegolius Labs repositories. The
normative statement of which repository owns which kind of truth is
`doc/authority-model.md` in `aegolius-labs/aio-agentic-sdlc`.

In the composed system this kit owns **layer 4**: a one-way projection of work
onto GitHub Issues and Projects for human and team visibility. It does not
decide what should be built. Used standalone, GitHub is the system of record
outright and no higher layer exists — that is a supported configuration, not a
degraded one.

Downstream state flows back as evidence, never as intent.

## Host manifests

The plugin ships one manifest per host, and they must agree:

- `.codex-plugin/plugin.json` — Codex
- `.claude-plugin/plugin.json` — Claude Code
- `.claude-plugin/marketplace.json` — Claude Code marketplace entry

`skills/` is the single source of truth for behavior and is auto-discovered by
both hosts. Do not fork skill content per host. `tests/test_host_manifest_parity.py`
enforces that `name`, `description`, and the base version agree across manifests;
build metadata after `+` may differ so each host can carry its own provenance.

Validate Claude Code manifests with the bundled validator:

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

## Installing locally

```powershell
claude plugin marketplace add F:\github\aegolius-labs\agentic-backlog-kit
claude plugin install agentic-backlog-kit@aegolius-labs-backlog
```

## Skill invocation

Skill bodies use Codex's `$skill-name` reference syntax when one skill points at
another. In Claude Code the equivalent is model invocation by description, or
`/agentic-backlog-kit:skill-name` typed explicitly. Read a `$name` reference as
"use that skill", not as a literal command to type.

## GitHub transport

The supported native transports are an authenticated `gh` CLI session or direct
GraphQL/REST via `GH_TOKEN` or `GITHUB_TOKEN`. These are peers under the same
plan, digest, apply, receipt, and refresh contract.

This repository deliberately ships **no** `.mcp.json`. Wave C evaluated the
installed generic GitHub MCP and recorded it as capability-incomplete for the
Projects surface, so it failed closed before any write. Declaring it as a Claude
Code MCP dependency would advertise a route the kit's own evidence says cannot
complete an apply. Revisit this with R13, not before.

## Verification

```powershell
python -c "import sys, unittest; sys.path.insert(0, 'src'); suite=unittest.defaultTestLoader.discover('tests'); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())"
python scripts/backlog.py --help
```

The Bash tool is also available on Windows here. The same suite runs with:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```
