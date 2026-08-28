# Narrow QA-kit interoperability boundary

R06 evaluates how Codex picks up and runs the backlog plugin. It does not
implement QA workflows and does not import, invoke, or modify the separate
`agentic-qa-kit` checkout. In particular, the unfinished `qa-workflow` and
`qa-backlog-handoff` skills remain outside this plugin's activation surface.

The complementary boundary is a small handoff contract:

| Concern | Backlog kit owns | QA kit may provide/consume |
| --- | --- | --- |
| Work identity | Stable backlog `id`, type, parent, dependencies, status, and maturity | Reference the stable ID; never mint a competing ID |
| Acceptance | `acceptance_criteria` on the backlog item | Use those criteria as the test target; report gaps rather than rewriting them silently |
| Evidence | Digest-bound plans, receipts, and synchronization state | Provide a redacted evidence reference, result status, and artifact digest |
| Mutation authority | GitHub issue/Project writes after explicit plan-digest confirmation | Never treat a QA result or handoff as write authorization |

A future handoff can therefore carry only `backlog_id`, the observed
acceptance-criteria outcome, `evidence_id`/artifact digest, and a redaction
status. The QA system remains responsible for discovery, reproduction, and
evidence collection; the backlog system remains responsible for stable IDs,
planning, and authorized GitHub mutation. This is intentionally a data
boundary, not a runtime dependency or a trigger for the placeholder skills.
