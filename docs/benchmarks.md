# Token and byte benchmarks

R09 uses a deterministic, model-free benchmark to protect the context shape of
the local backlog commands. Run it from the repository root with:

```powershell
python scripts/benchmark.py --check
```

The command generates the same 100-, 1,000-, and 10,000-item fixtures on every
run. It does not contact GitHub and does not make model calls. A report can be
saved for review with `--output path/to/report.json`; the report includes a
SHA-256 digest for every serialized payload so a byte-count change is easy to
trace.

## Method

The fixture uses stable IDs, a fixed iteration date, deterministic status/type
mixes, and a shallow dependency fan-out. The benchmark calls the same pure
Python functions used by `summary`, `show`, `next`, `prioritize`, and
`sprint-plan`. It also serializes a GitHub-shaped managed snapshot and a cold
sync plan (an empty remote, so every generated item is planned).

Measurements are canonical UTF-8 JSON with sorted keys, compact separators,
and one trailing newline. `bytes` is the authoritative regression signal.
`estimated_tokens` is a dependency-free planning approximation of
`ceil(bytes / 4)`; it is intentionally not a model-tokenizer claim. The report
also records pretty-printed sizes to show the display-format overhead.

The benchmark measures serialized data, not elapsed time. Timing varies with
the host, Python build, and CI load and would make an unreliable context-size
gate.

## Baselines and budgets

These are the compact-JSON baselines produced by generator
`r09-representative-v1` on 2026-08-27. Each cell is `bytes (estimated tokens)`.

| Operation | 100 items | 1,000 items | 10,000 items |
| --- | ---: | ---: | ---: |
| `summary` | 115 (29) | 123 (31) | 131 (33) |
| `show` | 569 (143) | 569 (143) | 569 (143) |
| `next` | 180 (45) | 180 (45) | 181 (46) |
| `prioritize` (limit 20) | 3,494 (874) | 3,485 (872) | 3,486 (872) |
| `sprint-plan` | 5,591 (1,398) | 46,973 (11,744) | 460,814 (115,204) |
| `sprint-plan --skipped-limit 50` | 3,773 (944) | 3,768 (942) | 3,770 (943) |
| `snapshot` artifact | 75,240 (18,810) | 753,349 (188,338) | 7,552,509 (1,888,128) |
| cold `sync-plan` artifact | 62,860 (15,715) | 627,618 (156,905) | 6,275,893 (1,568,974) |

Budgets for linear outputs leave approximately 20–30% headroom over the
observed large-backlog slope; fixed-size command budgets are small absolute
envelopes chosen to keep model-facing responses bounded:

| Operation | Fixed allowance | Per-item allowance | 10,000-item byte envelope |
| --- | ---: | ---: | ---: |
| `summary` | 512 | 0 | 512 |
| `show` | 1,024 | 0 | 1,024 |
| `next` | 512 | 0 | 512 |
| `prioritize` | 6,144 | 0 | 6,144 |
| `sprint-plan` | 8,192 | 58 | 588,192 |
| `sprint-plan-compact` (`--skipped-limit 50`) | 8,192 | 0 | 8,192 |
| `snapshot` artifact | 16,384 | 900 | 9,016,384 |
| cold `sync-plan` artifact | 16,384 | 750 | 7,516,384 |

The `--check` gate fails when any measured compact payload exceeds its
operation envelope. Because the budgets are byte-based and the fixture is
fixed, the check is CI-friendly and does not depend on network state or model
availability.

## Interpreting large artifacts

The snapshot and full sync plan are disposable files used for reconciliation;
they are not intended to be pasted into model context. Use the existing output
options so the command response contains only a path/count/digest summary:

```powershell
python scripts/backlog.py snapshot --output .agentic-backlog/cache/remote.json
python scripts/backlog.py sync-plan `
  --snapshot .agentic-backlog/cache/remote.json `
  --output .agentic-backlog/cache/sync-plan.json
python scripts/backlog.py sprint-plan --skipped-limit 50
```

The benchmark makes the linear artifact cost visible rather than hiding it.
The fixed-size `prioritize` response is capped at 20 items. A full
`sprint-plan` includes a reason for every skipped item, so its serialized
preview grows linearly. When that preview is model-facing, pass
`--skipped-limit 50`; the response then includes a bounded sample plus
`skipped_count` and `skipped_truncated` metadata. The full mapping remains
available by default for local inspection and machine use.
