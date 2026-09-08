# Contributing

Issue reports, design discussion, and documentation feedback are welcome after the repository is published.

This project uses a noncommercial plus paid-commercial dual-licensing model. Aegolius Labs must have sufficient rights to distribute every code contribution under both models. Until a contributor agreement process is published, external code pull requests cannot be accepted or merged. This avoids accepting code under terms that would make commercial licensing ambiguous.

Do not submit code copied from `aio-agentic-sdlc` or another project unless its license is compatible and the source and license are clearly identified. Never submit secrets or private backlog data.

Development changes should preserve the invariants in [AGENTS.md](AGENTS.md), include tests proportional to risk, and pass the complete local suite.

Commits intended for `main` use Conventional Commits. `fix:` selects a patch
release, `feat:` selects a minor release, and a `BREAKING CHANGE:` footer or
breaking `!` selects a major release. Other commit types do not release by
default. A release-bearing change must also update `pyproject.toml`,
`.codex-plugin/plugin.json`, `src/agentic_backlog_kit/__init__.py`, and the
corresponding `CHANGELOG.md` release heading to the same next semantic version.
The organization workflow computes that version independently and stops before
creating a tag if these files disagree.
