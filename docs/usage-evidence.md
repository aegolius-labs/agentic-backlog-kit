# Usage evidence

The kit can record how it is used in a project, so that its owner has
evidence of use beyond their own word. It follows the organization's
[usage evidence contract](https://github.com/aegolius-labs/.github/blob/main/docs/usage-evidence.md),
which every Aegolius Labs kit shares.

Recording is off unless a project opts in. A project that never runs
`usage enable` gets no usage files and no `.gitignore` change.

## Opting in

```bash
python scripts/backlog.py usage enable
```

This creates `.aegolius-usage/config.json` with a random project id and adds
`.aegolius-usage/` to `.gitignore`, so nothing is committed. Run it again and
nothing changes.

From then on each command appends one line to `.aegolius-usage/events.jsonl`:
the command name, `ok`, `refused` or `error`, a fixed error code such as
`GitHubApiError`, the kit version, and the host and initiator. Nothing from the
project is recorded: no paths, arguments, repository names, issue text or
error messages. The `usage` commands themselves are not recorded.

The host is `claude-code` when `CLAUDECODE=1` is set, or whatever
`AEGOLIUS_USAGE_HOST` names; otherwise `unknown`. The initiator comes only from
`AEGOLIUS_USAGE_INITIATED_BY` (`person` or `agent`), and `AEGOLIUS_USAGE_RUN_ID`
groups the events of one workflow. The kit never guesses either.

## Feedback

```bash
python scripts/backlog.py usage feedback --verdict helped --source agent-judgment \
  --friction "the plan digest had to be copied by hand"
```

`--verdict` is `helped`, `neutral` or `got_in_the_way`. `--source` is `person`
for the user's own words and `agent-judgment` for a model's opinion; reports
keep the two apart and label agent judgment as such. At most five friction
phrases of 80 characters each are accepted, and a phrase that looks like a
path, URL, email, token or hash is rejected.

## Reporting and publishing

`usage report` prints counts as JSON, or as Markdown with `--share`. Pass
`--root` more than once to combine projects. Any count under 5 is shown as
`<5`, and the success rate is withheld until there is enough to show.

`usage publish` posts the Markdown report as one comment on an issue named
after the project id, in a repository the owner chose. It refuses until the
owner adds a `publish` object (`repository`, `authorized_by`,
`authorized_at`) to `config.json` by hand. No command writes that object.

## Turning it off

`usage disable` stops recording and keeps what exists. `usage purge` deletes
the folder.
