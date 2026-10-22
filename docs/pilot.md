# Outside pilot guide

This page is for a team outside Aegolius Labs that has agreed to pilot the
kit. It is R34, and production readiness gate 12: the kit is not called 1.0
until a team other than ours has relied on it.

## What a pilot is

Your team points the kit at one of its own GitHub repositories, manages a real
backlog with it for at least one sprint, and tells us where it fell short. You
keep using GitHub exactly as you do now. The kit only adds issues, fields and
views that you have reviewed and confirmed first; it never deletes an issue and
never closes one because it stopped being listed.

## Who fits

- A noncommercial team of two or more that already plans work in GitHub Issues, or wants to (see Licensing below).
- A repository owned by an organization or a personal account, with its
  GitHub Project owned by the same account.
- One repository. Cross-repository backlogs are out of scope for now.
- Someone who will use Claude Code or Codex as the agent host. The engine also
  runs on its own from the command line.
- github.com, not GitHub Enterprise Server.

## Licensing

A pilot runs under the kit's ordinary
[PolyForm Noncommercial License](../LICENSE.md), with no separate agreement
(owner decision, 2026-10-15). That means the pilot team and its use must be
noncommercial: for example an open-source project maintained by individuals, a
student or research group, or a nonprofit. Use by or for a for-profit
organization, including evaluating the kit for one, needs a commercial license
first; see [COMMERCIAL.md](../COMMERCIAL.md). Such a team is not a pilot under
this guide.

## Timeline

| Week | You do | We do |
| --- | --- | --- |
| 0 | A 30-minute kickoff call; agree which repository and Project | Confirm your setup meets the supported configuration |
| 1 | Follow the [quickstart](quickstart.md) to a first converged sync, or adopt your existing issues with `backlog-adopt` | Answer questions within one working day |
| 1-3 | Plan and run at least one sprint with the kit: ingest new work, prioritize, plan the sprint, sync | Fix blocking defects first; ship them as patch releases |
| 3 | A 30-minute retrospective call | Write up the results with you |

## What we ask of you

- **A friction log.** Every time you were confused, blocked, surprised, or had
  to work around the kit, one line with the date and what happened. Rough notes
  are better than polished ones.
- **Issues for defects** in
  [aegolius-labs/agentic-backlog-kit](https://github.com/aegolius-labs/agentic-backlog-kit/issues),
  with the kit release or commit you installed and the command you ran.
- **Plans and receipts on request.** If something went wrong, the plan JSON and
  the apply receipt under `.agentic-backlog/receipts/` let us reproduce it. They
  contain your issue titles and numbers; redact anything private before sharing.
  Never send tokens or credentials.
- **The retrospective.** Would you keep using it, and what would have to change
  for you to?

## What counts as success

The pilot proves gate 12 when your team has:

1. reached a converged sync (a fresh `sync-plan` reports zero actions) on your
   own repository without a maintainer running commands for you;
2. planned and finished at least one sprint with the kit; and
3. recorded the friction log and retrospective above.

A pilot that ends early because the kit did not fit is still useful evidence,
and is recorded as such. It does not meet the gate.

## Safety

Every write to GitHub is shown to you as a plan first and runs only after you
confirm its digest. The one exception is a plan made solely of Priority field
updates, which the kit applies after showing it. Your manifest
(`.agentic-backlog/manifest.json`) lives in your repository; generated caches and
receipts are not meant to be committed. If you stop the pilot, your issues,
Project and views stay exactly as they are and keep working without the kit.
