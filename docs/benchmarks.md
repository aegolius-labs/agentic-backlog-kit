# Token, byte and API-call benchmarks

R09 uses a deterministic, model-free benchmark to protect the context shape of
the local backlog commands. Run it from the repository root with:

```powershell
python scripts/benchmark.py --check
```

The command generates the same 100-, 1,000-, and 10,000-item fixtures on every
run for byte budgets, and 100-, 1,000- and 5,000-issue fixtures for
[API-call budgets](#api-call-budgets). It does not contact GitHub and does not
make model calls. A report can be
saved for review with `--output path/to/report.json`; the report includes a
SHA-256 digest for every serialized payload so a byte-count change is easy to
trace.

## Coverage boundary

The existing shallow-fixture byte budgets do not establish support for deep
chains or runtime performance. The review reproduced RecursionError on a valid
1,200-item chain. [R17](remediation-plan.md#r17-remove-dependency-depth-sensitivity-f5)
proposes iterative traversal and dedicated 1,200/10,000-node correctness tests.
Those tests are pending and must not be inferred from the existing 10,000-item
payload benchmark.

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
The release-candidate rerun after Wave B's view and iteration changes produced
these values; that report's SHA-256 was
`0c8e76542847797eda4d30c764476599cc253e1725fd339d889e83df846addf3` and it was
byte-for-byte identical on Windows and local Ubuntu WSL.

R15 and R18 changed one row. Completed work now scores zero and is released
first so it cannot hold back its dependents, which reorders the ranked head
wherever a fixture contains completed items and slightly shrinks the
`prioritize` window. Every other operation is unchanged. R16 then changed the two sprint rows. A plan now reports the work already
committed to the target sprint and the work committed elsewhere, so the
unbounded `sprint-plan` grows with those lists while the 100-item case shrinks
slightly - work withheld as carryover is reported once rather than duplicated
into `skipped`. The projected variant grows because `--skipped-limit` now bounds
the retained and carryover lists as well, which is what keeps the 1,000- and
10,000-item cases flat at roughly 8 KB instead of scaling with the backlog.

The current report SHA-256 is
`5d43f3dae4f4fe5b821840bbe6fa5a8f47852d0f817d024ed1318a6e98746bdc`. It covers
the API-call section below as well; the byte measurements in the table are
unchanged by S-R28-3 and S-R29-2.

| Operation | 100 items | 1,000 items | 10,000 items |
| --- | ---: | ---: | ---: |
| `summary` | 115 (29) | 123 (31) | 131 (33) |
| `show` | 569 (143) | 569 (143) | 569 (143) |
| `next` | 180 (45) | 180 (45) | 181 (46) |
| `prioritize` (limit 20) | 3,455 (864) | 3,362 (841) | 3,362 (841) |
| `sprint-plan` | 5,990 (1,498) | 55,718 (13,930) | 555,449 (138,863) |
| `sprint-plan --skipped-limit 50` | 4,947 (1,237) | 8,100 (2,025) | 8,150 (2,038) |
| `snapshot` artifact | 75,240 (18,810) | 753,349 (188,338) | 7,552,509 (1,888,128) |
| cold `sync-plan` artifact | 72,319 (18,080) | 720,417 (180,105) | 7,202,332 (1,800,583) |

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
| cold `sync-plan` artifact | 16,384 | 815 | 8,166,384 |

The `--check` gate fails when any measured compact payload exceeds its
operation envelope. Because the budgets are byte-based and the fixture is
fixed, the check is CI-friendly and does not depend on network state or model
availability.

## API-call budgets

GitHub rate-limits by request, so a change that adds one call per issue is
invisible to the byte budgets yet caps how large a backlog can sync in an hour.
S-R28-3 counts transport calls for each phase at 100, 1,000 and 5,000 issues
and fails `--check` when a phase exceeds its budget.

The counts come from running the real snapshot reader, sync planner and plan
executor against an in-memory repository and organization Project
(`agentic_backlog_kit.api_benchmark.SimulatedGitHub`). It answers exactly the
REST and GraphQL requests those components send and fails on any other, so a
new kind of call cannot go uncounted. It does not contact GitHub, and the
counts are a pure function of the fixture. Use `--api-size` to measure other
sizes.

The phases are:

- `snapshot`: one `snapshot` read of the converged repository.
- `plan`: `sync-plan` against that snapshot. Planning is pure and must make no
  call.
- `apply`: `sync-apply` of the resulting empty plan: the refresh read, the
  capability check, and the post-apply verification read (S-R29-2).
- `cold-apply`: `sync-apply` of a cold plan against an empty repository, so
  every item is created, added to the Project and written, then verified.

The benchmark also checks that the cold apply converges: re-planning against
the repository it produced must yield no actions.

Each cell is total calls (REST + GraphQL):

| Phase | 100 issues | 1,000 issues | 5,000 issues |
| --- | ---: | ---: | ---: |
| `snapshot` | 5 (2 + 3) | 41 (11 + 30) | 201 (51 + 150) |
| `plan` | 0 | 0 | 0 |
| `apply` (converged) | 10 (4 + 6) | 82 (22 + 60) | 402 (102 + 300) |
| `cold-apply` | 850 (125 + 725) | 8,464 (1,232 + 7,232) | 42,308 (6,156 + 36,152) |

Reads are paged: one issue-listing page per 100 issues, one Project page per
100 items and one batched relationship query per 50 issues (S-R28-1), about 40
calls per 1,000 issues. Writes are not: a cold apply costs one issue creation,
one Project add, and one field write per Project field for every item, plus a
call for each dependency. That is about 8.4 calls per issue, and no batching
endpoint exists for those mutations. A 5,000-issue cold sync is therefore a
multi-hour operation under GitHub's secondary limits, while a steady-state
sync of the same backlog costs about 400 calls: one read before the apply and
one to verify it. The simulated repository has no read-after-write lag, so
verification converges on its first read; each re-read GitHub's lag forces
costs one more snapshot.

Budgets are a fixed allowance plus an allowance per 1,000 issues, rounded up:

| Phase | Fixed allowance | Per 1,000 issues | 5,000-issue envelope |
| --- | ---: | ---: | ---: |
| `snapshot` | 4 | 50 | 254 |
| `plan` | 0 | 0 | 0 |
| `apply` (converged) | 8 | 100 | 508 |
| `cold-apply` | 8 | 8,600 | 43,008 |

The read budgets leave about 25% headroom over the paged slope. A regression to
one read per issue adds 1,000 calls per 1,000 issues and fails at every size.
The cold-apply headroom is kept below one call per issue, so losing the cached
Project metadata or adding a per-item write fails the check rather than
hiding inside the allowance.

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
