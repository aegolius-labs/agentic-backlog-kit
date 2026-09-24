# Production readiness - 2026-09-24

The question this answers: how far is the kit from a team other than ours
installing it, pointing it at their repository, and relying on it without
maintainer help. It was written on `main` at v0.11.0, after R25 shipped and the
kit's own backlog converged to a zero-action sync plan.

## Verdict

The engine is ready. The product is not. **3 of 12 production gates are met and
3 are partly met.** None of the gaps needs a redesign; each is tracked as an
item under `EPIC-PROD`.

## Gates

| # | Gate | State | Evidence | Item |
| --- | --- | --- | --- | --- |
| 1 | Correct, safe core engine | Met | 428 tests; every write is previewed and digest-confirmed with receipts; unsafe input and cycles are rejected before any write | - |
| 2 | Automated, verified releases | Met | 11 organization-managed releases through v0.11.0, all immutable; hosted recovery proven (R14) | - |
| 3 | Validated against real GitHub | Met | Wave C on both the CLI and direct-API routes; this repository's own backlog; adoption live test | - |
| 4 | Closes the work lifecycle | Open | R10 is refined into four ready stories; none is built | R10 |
| 5 | Stays within GitHub rate limits at real sizes | Open | Two REST calls per issue per snapshot, repeated by the apply refresh; about 1,200 issues an hour at 5,000 requests; no retry | R28 |
| 6 | Tells GitHub's lag apart from drift | Partly met | Documented, but resolved by hand; on 2026-09-24 the Project item list lagged over 25 minutes and produced a false residual plan | R29 |
| 7 | Installs without cloning, with a quickstart | Open | Install is documented from a local path only; no quickstart | R30 |
| 8 | Agent behavior verified on the current release | Open | Installed-plugin evaluation last ran on 0.1.0 in Codex; never end to end in Claude Code | R31 |
| 9 | CI covers supported platforms and Pythons | Partly met | Ubuntu and Python 3.11 only, against a `>=3.11` claim; Windows validated by hand | R32 |
| 10 | Supported configurations stated | Partly met | Every Project query is organization-scoped; the README implies it without saying so | R33 |
| 11 | Stability promise | Open | 0.x, Alpha classifier, manifest schema just moved to 2, no compatibility policy | R33 |
| 12 | Proven outside Aegolius Labs | Open | No external issues or users | R34 |

Licensing is not a gate but matters to any production user: the kit is
PolyForm Noncommercial, and for-profit use requires a separate paid agreement.

## Order

The owner chose on 2026-09-24 to put scale ahead of R10. The quickstart (S-R30-2)
depends on the rate-limit and lag work, because a quickstart invites real users
and they should not meet throttling failures or false drift on their first sync.
The resulting order from `abk next` is R28, then R29, then installation and
evaluation, then R10. R34 needs the owner to recruit a pilot.
