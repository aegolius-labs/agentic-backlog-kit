"""Observed-state evidence export (S-R35-3).

The `aio-agentic-sdlc` authority model composes three repositories: it owns
the Intention DAG (what should be built, layer 1) and the Reality DAG (what
is, layers 2-3); this kit is layer 4, a one-way projection of accepted work
onto GitHub Issues and Projects. `docs/authority-model.md` in
`aio-agentic-sdlc` states the rule this module exists to serve: **downstream
state flows back as evidence, never as intent.**

`observed_state` renders exactly that: a snapshot of what GitHub currently
reports about issues this kit manages, in a small versioned contract another
system can consume without importing this repository. Every field here is an
observation, not a decision. Nothing in this document is, or should be
treated as, an edit to what should be built - not by this kit, and not by a
consumer. It also never writes to this kit's own manifest; the manifest
stays intent-only, exactly as `docs/operational-authority.md` (decision D1)
requires.

Versioning: adding a field is additive and keeps `contract_version` the same.
Renaming or removing a field, or changing what an existing field means, must
bump `contract_version`.
"""

from __future__ import annotations

from typing import Any

from . import __version__
from .execution import state_fingerprint
from .sync import extract_guid

CONTRACT = "abk-observed-state"
CONTRACT_VERSION = 1


def _observed_item(
    issue: dict[str, Any], *, manifest_ids: set[str], sprint_field: str
) -> dict[str, Any]:
    fields = issue.get("project_fields") or {}
    in_project = bool(issue.get("in_project", False))
    entry: dict[str, Any] = {
        "item_id": issue["abk_id"],
        "guid": issue.get("guid") or extract_guid(issue.get("body")) or None,
        "issue_number": issue["number"],
        "state": issue.get("state"),
        "status": fields.get("Status") if in_project else None,
        "sprint": fields.get(sprint_field) if in_project else None,
        "in_project": in_project,
        "in_manifest": issue["abk_id"] in manifest_ids,
    }
    url = issue.get("url")
    if url:
        entry["url"] = url
    closed_at = issue.get("closed_at")
    if closed_at:
        entry["closed_at"] = closed_at
    return entry


def observed_state(
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
    observed_at: str,
    route: str,
) -> dict[str, Any]:
    """Render one observed-state evidence document.

    `manifest` supplies the target identity and which issues it already
    knows (`in_manifest`); `snapshot` is exactly what a `GitHubSnapshotReader`
    (or the auto-fresh cache wrapping one) returned - no additional GitHub
    calls are made here. `observed_at` is the snapshot's own timestamp (an
    explicit `--offline-snapshot` file that carries none may pass the moment
    of export instead), and `route` names how the data was obtained: the
    resolved `--backend` (`"gh"` or `"api"`) for a fresh fetch, `"cache"` for
    the auto-refreshed cache, or `"offline-snapshot"` for an exact file.

    This is evidence about reality, not a description of what should be
    built: a consumer folds it into its own Reality DAG (or equivalent) as an
    observation, never as an Intent IR edit.
    """

    github = manifest["github"]
    manifest_ids = {entry["id"] for entry in manifest.get("items", [])}
    iteration = (manifest.get("workflow") or {}).get("iteration") or {}
    sprint_field = iteration.get("field", "Sprint")

    issues = snapshot.get("issues", [])
    items = sorted(
        (
            _observed_item(issue, manifest_ids=manifest_ids, sprint_field=sprint_field)
            for issue in issues
        ),
        key=lambda entry: entry["item_id"],
    )
    unmanaged_issue_count = snapshot.get("unmanaged_issue_count", 0)

    document: dict[str, Any] = {
        "contract": CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "observed_at": observed_at,
        "source": {
            "tool": "agentic-backlog-kit",
            "version": __version__,
            "route": route,
        },
        "target": {
            "owner": github["owner"],
            "repository": github["repository"],
            "project_number": github["project_number"],
        },
        "items": items,
        "unmanaged_issue_count": unmanaged_issue_count,
    }
    document["digest"] = f"sha256:{state_fingerprint(document)}"
    return document
