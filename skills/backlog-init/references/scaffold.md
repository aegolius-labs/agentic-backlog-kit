# GitHub scaffold contract

Bootstrap discovers open organization Projects and their repository links. A requested number selects exactly that Project; a requested title uses exact title equality. Without either selector, the unique open Project linked to the repository or titled like the repository is selected. Multiple candidates fail closed. No candidate produces a reviewed `project.create` action whose creation links the repository.

After creation, the command captures the returned node ID, number, title, and URL, writes the number to the manifest, and refreshes GitHub before planning fields or views. This avoids assuming that a newly created Project has empty default state. The scaffold adds missing structures, extends an existing Status field while preserving option IDs, and fails closed on incompatible same-name fields or views.

Fields:

- `Status`: single-select using manifest workflow statuses.
- `Sprint`: iteration using the manifest start date and duration.
- `Impact`, `Effort`, `Business Value`, `Enabler Value`, `Priority`: number fields.

Repository labels provide issue-type fallback: `type:initiative`, `type:epic`, `type:feature`, `type:story`, `type:bug`, and `type:task`.

Views:

- `Backlog`: table, all issues, Priority descending.
- `Kanban`: open issues, board columns from Status.
- `Current Sprint`: `Sprint:@current`, board columns from Status.
- `Roadmap`: open work excluding Status Done.

Commands:

```text
python <plugin-root>/scripts/backlog.py init-plan --owner OWNER --repository REPO [--project-title TITLE] [--project-number N] --output .agentic-backlog/cache/bootstrap-plan.json
python <plugin-root>/scripts/backlog.py init-apply --plan .agentic-backlog/cache/bootstrap-plan.json --confirm DIGEST --scaffold-plan .agentic-backlog/cache/scaffold-plan.json
python <plugin-root>/scripts/backlog.py scaffold-snapshot --output .agentic-backlog/cache/scaffold.json
python <plugin-root>/scripts/backlog.py scaffold-plan --snapshot .agentic-backlog/cache/scaffold.json --output .agentic-backlog/cache/scaffold-plan.json
python <plugin-root>/scripts/backlog.py scaffold-apply --plan .agentic-backlog/cache/scaffold-plan.json --confirm DIGEST --receipt .agentic-backlog/receipts/scaffold-apply.json
```

The plan digest binds the validated manifest, scaffold snapshot, and per-action
preconditions. Apply obtains a new scaffold snapshot and aborts before mutation
if rebuilding changes that digest. The receipt records the completed prefix and
any failed action; interruption is resumed only through a fresh reviewed plan.

The GitHub token/session needs repository Issues write permission and organization Projects read/write permission. Project creation uses GitHub's `createProjectV2` GraphQL mutation with `repositoryId`; selecting an unlinked Project uses `linkProjectV2ToRepository`. Creating organization issue types is not automatic; `native_or_label` tries an existing native type and falls back to the managed label.

GitHub API contracts: [Projects GraphQL reference](https://docs.github.com/en/graphql/reference/projects) and [API guide for Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects).
