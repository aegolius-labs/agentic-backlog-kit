# Installed-plugin evaluation

This is the Wave C R06 preparation and evidence harness for the
`agentic-backlog-kit` skills-only plugin. It stages a complete copy of the
checkout under a generated workspace and writes a workspace-local
`.agents/plugins/marketplace.json`. Nothing in this flow edits a personal
marketplace, calls GitHub, or claims that Codex activated a skill.

The corpus follows the [official complete-plugin test flow](https://developers.openai.com/plugins/deploy/connect-chatgpt#test-the-complete-plugin):
each case starts in a fresh task and records direct, indirect, follow-up,
negative, boundary, and write-confirmation behavior. Every case is run once
with GitHub MCP available and once with it unavailable. The latter run must
show the documented CLI/API fallback for workflows that need GitHub; local
ingestion, prioritization, and planning remain local-engine operations.

## Prepare and inspect locally

```powershell
python scripts/installed_plugin_eval.py prepare `
  --output .agentic-backlog/evals/installed-plugin/r06-local `
  --run-id r06-local
python scripts/installed_plugin_eval.py show `
  --suite .agentic-backlog/evals/installed-plugin/r06-local/suite.json
python scripts/installed_plugin_eval.py diagnose `
  --suite .agentic-backlog/evals/installed-plugin/r06-local/suite.json
```

`prepare` creates these important artifacts below the requested output path:

- `workspace/.agents/plugins/marketplace.json`: a local marketplace containing
  one `AVAILABLE` `agentic-backlog-kit` entry with `ON_INSTALL` authentication.
- `workspace/plugins/agentic-backlog-kit/`: the staged plugin checkout whose
  manifest and bundled references are checked before the suite is written.
- `fixtures/evaluation-corpus.json`: the immutable prompt corpus copy.
- `suite.json`: the run ID, manifest/corpus digests, executor matrix, case
  expectations, and result contract.

The generated `workspace` is the safe place for the app-side test. Add that
workspace-local marketplace through the Codex Plugins Directory, install the
plugin, restart/reload if required by the app, and start a new task with the
plugin enabled. Do not copy this generated marketplace into a personal
`~/.agents/plugins/marketplace.json` unless the user explicitly chooses that
installation path and performs the edit themselves.

The optional CLI probe is read-only and only asks the installed executable for
`--help` and `--version`:

```powershell
python scripts/installed_plugin_eval.py diagnose `
  --suite .agentic-backlog/evals/installed-plugin/r06-local/suite.json `
  --run-cli
```

An unavailable or access-denied executable is recorded as a diagnostic; it is
not silently treated as an installed-task pass.

## Record and verify fresh-task results

For each corpus case, retain the prompt hash, activation decision, selected
skill, references used/resolved, confirmation request and response, authorization
decision, mutation flag, and redacted result. Record both executor runs in one
JSON object per case. A result has this shape (the harness also accepts JSON
instead of NDJSON for convenience):

```json
{
  "case_id": "direct-ingest",
  "category": "direct",
  "fresh_task": true,
  "executor_runs": [
    {
      "mode": "mcp_available",
      "github_mcp": "available",
      "transport": "local-engine",
      "fallback_used": false,
      "turns": [
        {
          "prompt_sha256": "<sha256 of the corpus prompt>",
          "activated": true,
          "plugin": "agentic-backlog-kit",
          "skill": "backlog-ingest",
          "references": ["skills/backlog-ingest/references/item-contract.md"],
          "references_resolved": true,
          "confirmation": {"requested": false, "provided": false},
          "authorization": {"decision": "not_applicable", "mutated": false},
          "tool_calls": []
        }
      ]
    },
    {
      "mode": "mcp_unavailable",
      "github_mcp": "unavailable",
      "transport": "local-engine",
      "fallback_used": false,
      "turns": ["...same redacted turn shape..."]
    }
  ]
}
```

Write records with the local command, then verify:

```powershell
python scripts/installed_plugin_eval.py record `
  --suite .agentic-backlog/evals/installed-plugin/r06-local/suite.json `
  --input ./redacted-results.ndjson
python scripts/installed_plugin_eval.py verify `
  --suite .agentic-backlog/evals/installed-plugin/r06-local/suite.json `
  --report .agentic-backlog/evals/installed-plugin/r06-local/report.json
```

`synthetic` can generate schema-valid records for testing the verifier, but
those records are explicitly not evidence of a Codex run:

```powershell
python scripts/installed_plugin_eval.py synthetic `
  --suite .agentic-backlog/evals/installed-plugin/r06-local/suite.json
```

The verifier fails on missing/duplicate cases, stale prompts, non-fresh tasks,
unexpected activation, missing bundled references, missing MCP fallback runs,
or any mutation without an exact reviewed digest confirmation. Negative and
boundary cases must have no selected skill, plugin tool call, or mutation.

## What remains an app/user gate

The repository can prove manifest shape, local marketplace resolution, bundled
reference paths, corpus completeness, result shape, and authorization-oracle
behavior offline. It cannot prove model routing or a real install. The root
operator must still install the staged plugin in the Codex app, create a fresh
task for each case and executor mode, preserve redacted conversation results,
and review the verifier report. If the app's CLI is inaccessible, the report
must retain that diagnostic and leave R06's installed-task result pending.

An installed/enabled version is not sufficient evidence if a fresh task or
independent subagent does not expose the plugin skills in its session catalog.
Treat that condition as a catalog/reload blocker, restart or reload the app,
and rerun the fresh-task checks. Do not replace missing installed-skill
evidence with activation observed from the source checkout.
