# Agentic Backlog Kit

A Codex-first plugin for managing GitHub Issues and Projects as a structured, deterministic Agile backlog.

The kit combines focused skills with a zero-runtime-dependency Python engine. Agents use natural language for judgment-heavy work such as idea refinement, then hand validation, scoring, sprint packing, remote discovery, and synchronization to deterministic code. This keeps large backlogs out of model context and makes mutations reviewable.

## What is included

- `Initiative -> Epic -> Feature -> Story/Bug -> Task` hierarchy backed by GitHub sub-issues.
- Native GitHub issue dependencies for blocking relationships.
- Impact, Effort, Business Value, Enabler Value, and recursive dependency scoring.
- Dependency-safe, capacity-aware sprint planning against refreshed active/completed iteration state.
- Organization Project discovery/creation plus scaffolding for Status, Sprint, scoring fields, fallback type labels, and four fully reconciled views: Backlog, Kanban, Current Sprint, and Roadmap.
- Native GitHub Projects workflows through any complete supported transport: the Codex GitHub integration/GitHub MCP, authenticated GitHub CLI, or direct GraphQL/REST API.
- Dry-run planning by default and digest-confirmed apply operations.
- Compact per-item ingestion and optimistic, atomic manifest updates.

GitHub currently supports nested sub-issues, issue dependencies, issue types, Project iteration fields, and programmatic Project views. The kit maps directly to those native capabilities rather than encoding relationships only in issue text. See the [GitHub Issues documentation](https://docs.github.com/en/issues/tracking-your-work-with-issues/learning-about-issues/about-issues) and [Project view API](https://docs.github.com/en/rest/projects/views).

## Install for local plugin testing

This repository is the plugin source. Add it to a local marketplace, install it from the Plugins Directory, and start a new task with the plugin enabled, following OpenAI's [complete-plugin test flow](https://developers.openai.com/plugins/deploy/connect-chatgpt#test-the-complete-plugin). A machine-specific personal marketplace entry is intentionally not committed to this public repository.

## Quick start

Discover a matching organization Project or preview creation from only the organization and repository:

```powershell
python scripts/backlog.py init-plan `
  --owner aegolius-labs `
  --repository your-repository `
  --output .agentic-backlog/cache/bootstrap-plan.json
python scripts/backlog.py init-apply `
  --plan .agentic-backlog/cache/bootstrap-plan.json `
  --confirm <reviewed-digest> `
  --scaffold-plan .agentic-backlog/cache/scaffold-plan.json
```

Add `--project-title TITLE` or `--project-number N` to select explicitly. Ambiguous exact matches stop without mutation. `init-apply` records the resulting Project number in the manifest and refreshes GitHub before proposing scaffold changes. If a known Project number already exists, the legacy local-only `init` command remains available.

Validate and inspect local backlog data without contacting GitHub:

```powershell
python scripts/backlog.py validate
python scripts/backlog.py summary
python scripts/backlog.py prioritize --limit 10
python scripts/backlog.py next
python scripts/backlog.py sprint-plan --capacity 20
```

Preview GitHub Project scaffolding, then apply only the exact reviewed digest:

```powershell
python scripts/backlog.py scaffold-snapshot --output .agentic-backlog/cache/scaffold.json
python scripts/backlog.py scaffold-plan `
  --snapshot .agentic-backlog/cache/scaffold.json `
  --output .agentic-backlog/cache/scaffold-plan.json
python scripts/backlog.py scaffold-apply `
  --plan .agentic-backlog/cache/scaffold-plan.json `
  --confirm <reviewed-digest> `
  --receipt .agentic-backlog/receipts/scaffold-apply.json
```

Resolve or safely extend the iteration schedule, then plan only against refreshed Project state:

```powershell
python scripts/backlog.py iteration-plan `
  --snapshot .agentic-backlog/cache/scaffold.json `
  --target @next `
  --as-of 2026-08-27 `
  --output .agentic-backlog/cache/iteration-plan.json
python scripts/backlog.py iteration-apply `
  --plan .agentic-backlog/cache/iteration-plan.json `
  --confirm <reviewed-digest> `
  --receipt .agentic-backlog/receipts/iteration-apply.json
python scripts/backlog.py scaffold-snapshot --output .agentic-backlog/cache/scaffold.json
python scripts/backlog.py sprint-plan `
  --capacity 20 `
  --sprint @next `
  --snapshot .agentic-backlog/cache/scaffold.json
```

Iteration updates preserve the observed active schedule and require a post-apply refresh to verify GitHub-owned IDs before work can be assigned. Completed, overlapping, duplicate, stale/gapped, or ambiguous targets fail before mutation.

Use the same workflow for issues and Project items:

```powershell
python scripts/backlog.py snapshot --output .agentic-backlog/cache/remote.json
python scripts/backlog.py sync-plan `
  --snapshot .agentic-backlog/cache/remote.json `
  --output .agentic-backlog/cache/sync-plan.json
python scripts/backlog.py sync-apply `
  --plan .agentic-backlog/cache/sync-plan.json `
  --confirm <reviewed-digest> `
  --receipt .agentic-backlog/receipts/apply.json
```

Apply commands do not trust saved snapshots. They refresh GitHub, rebuild the
plan against the current validated manifest, and abort before the first write
unless its digest still matches the reviewed plan. Plans bind normalized local
and remote fingerprints and per-action preconditions. Receipts are updated
atomically after every action, so an interrupted run records its completed
prefix; refresh and create a new reviewed plan to resume safely.

The skills capability-check the host GitHub integration/MCP before using it. The launcher uses an authenticated `gh` session when selected, while `GH_TOKEN` or `GITHUB_TOKEN` enables the equally native direct GraphQL/REST route. Every route must produce the same canonical snapshots, plans, digests, and receipts; an incomplete MCP surface is reported explicitly, and write transports are never silently mixed within an apply. Project creation/linking needs organization Projects write access and repository Contents access; issue reconciliation also needs repository Issues write access. GitHub documents the additional Contents requirement when `createProjectV2` links a repository in its [Projects API guide](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects).

## Plugin UX

The plugin contains five focused skills:

- `$backlog-init` initializes the manifest and scaffolds the GitHub Project.
- `$backlog-ingest` turns ideas or requests into one validated backlog item at a time.
- `$backlog-prioritize` ranks work and selects the next executable item.
- `$backlog-sprint-plan` creates a dependency-safe capacity plan.
- `$backlog-sync-github` previews, validates, applies, and verifies GitHub reconciliation.

OpenAI plugins are universal packages that can be used by supported ChatGPT and Codex surfaces. This project is Codex-first because it relies on a coding workspace and local deterministic scripts, but its skills and GitHub MCP workflows remain portable. See the [OpenAI plugin architecture](https://developers.openai.com/plugins/concepts/plugins).

## Development

Run the complete test suite without installing dependencies:

```powershell
python -c "import sys, unittest; sys.path.insert(0, 'src'); suite=unittest.defaultTestLoader.discover('tests'); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())"
```

See [ROADMAP.md](ROADMAP.md) for delivery status and [docs/architecture.md](docs/architecture.md) for the source-of-truth and synchronization design.
The deterministic payload benchmark and its byte/token budgets are documented in [docs/benchmarks.md](docs/benchmarks.md).
Release-candidate Windows and local Linux/WSL validation evidence is recorded in [docs/validation.md](docs/validation.md).
The offline preparation and evidence contract for disposable live GitHub testing are documented in [evals/live_github/README.md](evals/live_github/README.md).

## License

Agentic Backlog Kit is source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE.md). Personal and other noncommercial uses permitted by that license are free. Any use in or for for-profit operations requires a separate paid license from Aegolius Labs; see [COMMERCIAL.md](COMMERCIAL.md).

Because commercial use is restricted, this is not an OSI-approved open-source license. See [docs/source-extraction.md](docs/source-extraction.md) for the clean adaptation boundary from the separately licensed source project reviewed during discovery.
