# GitHub scaffold contract

Bootstrap discovers open organization Projects and their repository links. A requested number selects exactly that Project; a requested title uses exact title equality. Without either selector, the unique open Project linked to the repository or titled like the repository is selected. Multiple candidates fail closed. No candidate produces a reviewed `project.create` action whose creation links the repository.

After creation, the command captures the returned node ID, number, title, and URL, writes the number to the manifest, and refreshes GitHub before planning fields or views. This avoids assuming that a newly created Project has empty default state. The scaffold adds missing structures and extends an existing Status field while preserving option IDs. It fails closed on incompatible same-name fields and on view state that current GitHub APIs cannot repair safely.

Fields:

- `Status`: single-select using manifest workflow statuses.
- `Sprint`: iteration using the manifest start date and duration.
- `Impact`, `Effort`, `Business Value`, `Enabler Value`, `Priority`: number fields.

Repository labels provide issue-type fallback: `type:initiative`, `type:epic`, `type:feature`, `type:story`, `type:bug`, and `type:task`.

Views:

- `Backlog`: table, all issues, ordered visible fields `Title`, `Status`, `Sprint`, `Priority`, `Impact`, `Effort`, `Business Value`, and `Enabler Value`; Priority descending.
- `Kanban`: open issues, visible fields `Title`, `Sprint`, `Priority`, and `Effort`; board columns from Status.
- `Current Sprint`: `Sprint:@current`, visible fields `Title`, `Priority`, and `Effort`; board columns from Status.
- `Roadmap`: roadmap layout over open work excluding Status Done. GitHub does not accept `visible_fields` for roadmap creation, so it is not managed for this view.

The scaffold snapshot records each view's node ID and number plus its normalized layout, filter, ordered visible fields, horizontal grouping, vertical grouping, and ordered sort criteria. Every field reference includes its GitHub node ID and REST database ID. View order is normalized by name while visible-field and sort order remain significant.

Missing views are created through GitHub's organization Project view REST endpoint. Filter, layout, and non-roadmap visible-field drift on an existing same-name view produces a reviewed `project.view.update` action using `updateProjectV2View`. GitHub's current update input does not expose grouping or sorting, so drift in `group_by`, `vertical_group_by`, or `sort_by` is a precise fail-closed conflict. Repair that setting in GitHub, refresh the snapshot, and re-plan. Do not delete and recreate the view.

Commands:

```text
python <plugin-root>/scripts/backlog.py init-plan --owner OWNER --repository REPO [--project-title TITLE] [--project-number N] --output .agentic-backlog/cache/bootstrap-plan.json
python <plugin-root>/scripts/backlog.py init-apply --plan .agentic-backlog/cache/bootstrap-plan.json --confirm DIGEST --scaffold-plan .agentic-backlog/cache/scaffold-plan.json
python <plugin-root>/scripts/backlog.py scaffold-snapshot --output .agentic-backlog/cache/scaffold.json
python <plugin-root>/scripts/backlog.py scaffold-plan --snapshot .agentic-backlog/cache/scaffold.json --output .agentic-backlog/cache/scaffold-plan.json
python <plugin-root>/scripts/backlog.py scaffold-apply --plan .agentic-backlog/cache/scaffold-plan.json --confirm DIGEST --receipt .agentic-backlog/receipts/scaffold-apply.json
python <plugin-root>/scripts/backlog.py iteration-plan --snapshot .agentic-backlog/cache/scaffold.json --target @next --as-of YYYY-MM-DD --output .agentic-backlog/cache/iteration-plan.json
python <plugin-root>/scripts/backlog.py iteration-apply --plan .agentic-backlog/cache/iteration-plan.json --confirm DIGEST --receipt .agentic-backlog/receipts/iteration-apply.json
```

The plan digest binds the validated manifest, complete scaffold snapshot, and per-action preconditions. Apply obtains a new scaffold snapshot and aborts before mutation if rebuilding changes that digest. View creation and update resolve field names to the freshly observed node and REST database IDs and reject identity changes. The receipt records the completed prefix and any failed action; interruption is resumed only through a fresh reviewed plan. Post-apply verification must yield zero view actions.

The GitHub token/session needs repository Issues write permission and organization Projects read/write permission. Creating or linking a Project to the repository also needs repository Contents permission. Project creation uses GitHub's `createProjectV2` GraphQL mutation with `repositoryId`; selecting an unlinked Project uses `linkProjectV2ToRepository`. Creating organization issue types is not automatic; `native_or_label` tries an existing native type and falls back to the managed label.

GitHub API contracts: [Projects GraphQL reference](https://docs.github.com/en/graphql/reference/projects), [Project view REST endpoints](https://docs.github.com/en/rest/projects/views), and [API guide for Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects).

Iteration snapshots retain the field ID, schedule start/duration, and canonical active/completed entries with ID, title, start date, duration, and completion state. Lifecycle updates are full-configuration replacements because GitHub documents provided iteration configuration as overwriting existing configuration. The mutation input cannot submit existing iteration IDs, so the reviewed plan repeats all active definitions, binds all observed IDs in preconditions, and verifies identity preservation after refresh. Completed or unsafe targets never produce a mutation.
