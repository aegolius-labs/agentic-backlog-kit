from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .execution import ApplyReceipt, Journal, receipt, state_fingerprint
from .manifest import ManifestError, default_manifest
from .scaffold import ScaffoldAction, build_scaffold_plan


class BootstrapAuthorizationError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class BootstrapPlan:
    owner: str
    repository: str
    project_title: str | None
    requested_project_number: int | None
    project: dict[str, Any] | None
    actions: list[ScaffoldAction]
    snapshot_fingerprint: str
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "repository": self.repository,
            "project_title": self.project_title,
            "requested_project_number": self.requested_project_number,
            "project": self.project,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "digest": self.digest,
            "action_count": len(self.actions),
            "actions": [action.as_dict() for action in self.actions],
        }


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    project: dict[str, Any]
    applied_actions: int
    receipt: ApplyReceipt


def _plan_digest(
    owner: str,
    repository: str,
    project_title: str | None,
    requested_project_number: int | None,
    project: dict[str, Any] | None,
    actions: list[ScaffoldAction],
    snapshot_fingerprint: str,
) -> str:
    canonical = json.dumps(
        {
            "owner": owner,
            "repository": repository,
            "project_title": project_title,
            "requested_project_number": requested_project_number,
            "project": project,
            "actions": [action.as_dict() for action in actions],
            "snapshot_fingerprint": snapshot_fingerprint,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _identity(project: dict[str, Any]) -> dict[str, Any]:
    try:
        identity = {
            "id": str(project["id"]),
            "number": int(project["number"]),
            "title": str(project["title"]),
            "url": str(project.get("url") or ""),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ManifestError("Discovered Project has incomplete identity") from exc
    if not identity["id"] or identity["number"] < 1 or not identity["title"]:
        raise ManifestError("Discovered Project has incomplete identity")
    return identity


def _select_project(
    projects: list[dict[str, Any]],
    repository: str,
    *,
    project_title: str | None,
    project_number: int | None,
) -> dict[str, Any] | None:
    active = [project for project in projects if not project.get("closed", False)]
    if project_number is not None:
        if isinstance(project_number, bool) or project_number < 1:
            raise ManifestError("Project number must be a positive integer")
        matches = [
            project for project in active if project.get("number") == project_number
        ]
        if not matches:
            raise ManifestError(
                f"Organization Project #{project_number} was not found or is closed"
            )
        selected = matches[0]
        if project_title is not None and selected.get("title") != project_title:
            raise ManifestError(
                f"Project #{project_number} is titled '{selected.get('title')}', "
                f"not '{project_title}'"
            )
        return selected

    if project_title is not None:
        matches = [project for project in active if project.get("title") == project_title]
    else:
        matches = [
            project
            for project in active
            if project.get("linked") is True or project.get("title") == repository
        ]
    matches.sort(key=lambda project: int(project.get("number", 0)))
    if len(matches) > 1:
        numbers = ", ".join(str(project.get("number")) for project in matches)
        selector = project_title if project_title is not None else repository
        raise ManifestError(
            f"Project discovery for '{selector}' is ambiguous; matching numbers: {numbers}"
        )
    return matches[0] if matches else None


def build_bootstrap_plan(
    owner: str,
    repository: str,
    discovery_snapshot: dict[str, Any],
    *,
    project_title: str | None = None,
    project_number: int | None = None,
) -> BootstrapPlan:
    """Select or create an organization Project, then plan its complete scaffold."""

    if not isinstance(owner, str) or not owner.strip():
        raise ManifestError("Owner must be a non-empty string")
    if not isinstance(repository, str) or not repository.strip():
        raise ManifestError("Repository must be a non-empty string")
    owner = owner.strip()
    repository = repository.strip()
    if project_title is not None:
        if not isinstance(project_title, str) or not project_title.strip():
            raise ManifestError("Project title must be a non-empty string")
        project_title = project_title.strip()
    if not isinstance(discovery_snapshot, dict):
        raise ManifestError("Project discovery snapshot must be an object")
    organization = discovery_snapshot.get("organization")
    remote_repository = discovery_snapshot.get("repository")
    projects = discovery_snapshot.get("projects")
    labels = discovery_snapshot.get("labels", [])
    if not isinstance(organization, dict) or organization.get("login") != owner:
        raise ManifestError("Discovery snapshot organization does not match requested owner")
    if (
        not isinstance(remote_repository, dict)
        or remote_repository.get("name") != repository
    ):
        raise ManifestError("Discovery snapshot repository does not match requested repository")
    if not isinstance(projects, list) or not isinstance(labels, list):
        raise ManifestError("Discovery snapshot projects and labels must be arrays")

    selected = _select_project(
        projects,
        repository,
        project_title=project_title,
        project_number=project_number,
    )
    actions: list[ScaffoldAction] = []
    if selected is None:
        title = project_title or repository
        owner_id = organization.get("id")
        repository_id = remote_repository.get("id")
        if not owner_id or not repository_id:
            raise ManifestError("Discovery snapshot lacks owner or repository node identity")
        actions.append(
            ScaffoldAction(
                "project.create",
                {
                    "owner_id": str(owner_id),
                    "repository_id": str(repository_id),
                    "title": title,
                },
                {"project": None},
            )
        )
        project_identity = None
        # A newly created Project can contain GitHub-managed default fields and views.
        # Discover it again before planning those mutations rather than guessing empty state.
        project_snapshot = None
        manifest_number = 1
    else:
        project_identity = _identity(selected)
        manifest_number = project_identity["number"]
        if not selected.get("linked", False):
            repository_id = remote_repository.get("id")
            if not repository_id:
                raise ManifestError("Discovery snapshot lacks repository node identity")
            actions.append(
                ScaffoldAction(
                    "project.link_repository",
                    {
                        "project_id": project_identity["id"],
                        "repository_id": str(repository_id),
                    },
                    {"project": project_identity, "linked": False},
                )
            )
        project_snapshot = {
            "fields": selected.get("fields", []),
            "views": selected.get("views", []),
            "labels": labels,
        }

    if project_snapshot is not None:
        scaffold = build_scaffold_plan(
            default_manifest(owner, repository, manifest_number), project_snapshot
        )
        actions.extend(scaffold.actions)
    snapshot_fingerprint = state_fingerprint(discovery_snapshot)
    digest = _plan_digest(
        owner,
        repository,
        project_title,
        project_number,
        project_identity,
        actions,
        snapshot_fingerprint,
    )
    return BootstrapPlan(
        owner,
        repository,
        project_title,
        project_number,
        project_identity,
        actions,
        snapshot_fingerprint,
        digest,
    )


def bootstrap_plan_from_dict(data: dict[str, Any]) -> BootstrapPlan:
    if not isinstance(data, dict) or not isinstance(data.get("actions"), list):
        raise ManifestError("Bootstrap plan must contain an actions array")
    owner = data.get("owner")
    repository = data.get("repository")
    project_title = data.get("project_title")
    requested_project_number = data.get("requested_project_number")
    project = data.get("project")
    if not isinstance(owner, str) or not isinstance(repository, str):
        raise ManifestError("Bootstrap plan must identify owner and repository")
    if project is not None and not isinstance(project, dict):
        raise ManifestError("Bootstrap plan project identity is malformed")
    if project_title is not None and not isinstance(project_title, str):
        raise ManifestError("Bootstrap plan Project title selector is malformed")
    if requested_project_number is not None and (
        not isinstance(requested_project_number, int)
        or isinstance(requested_project_number, bool)
        or requested_project_number < 1
    ):
        raise ManifestError("Bootstrap plan Project number selector is malformed")
    actions: list[ScaffoldAction] = []
    for index, raw in enumerate(data["actions"]):
        if (
            not isinstance(raw, dict)
            or not isinstance(raw.get("kind"), str)
            or not isinstance(raw.get("payload"), dict)
        ):
            raise ManifestError(f"Bootstrap action at index {index} is malformed")
        precondition = raw.get("precondition")
        if not isinstance(precondition, dict):
            raise ManifestError(f"Bootstrap action at index {index} is malformed")
        actions.append(ScaffoldAction(raw["kind"], raw["payload"], precondition))
    digest = data.get("digest")
    snapshot_fingerprint = data.get("snapshot_fingerprint")
    if not isinstance(digest, str) or digest != _plan_digest(
        owner,
        repository,
        project_title,
        requested_project_number,
        project,
        actions,
        snapshot_fingerprint,
    ):
        raise ManifestError("Bootstrap plan digest does not match its contents")
    if not isinstance(snapshot_fingerprint, str):
        raise ManifestError("Bootstrap plan snapshot fingerprint is malformed")
    return BootstrapPlan(
        owner,
        repository,
        project_title,
        requested_project_number,
        project,
        actions,
        snapshot_fingerprint,
        digest,
    )


class BootstrapExecutor:
    """Execute only bootstrap actions and retain the selected/created Project identity."""

    def __init__(self, service: Any) -> None:
        self.service = service
        self.project: dict[str, Any] | None = None

    def select(self, identity: dict[str, Any]) -> None:
        self.project = _identity(identity)
        self.service.use_project(self.project)

    def __call__(self, action: ScaffoldAction) -> None:
        if action.kind == "project.create":
            self.project = _identity(self.service.create_project(action.payload))
        elif action.kind == "project.link_repository":
            self.service.link_project_repository(action.payload)
        elif action.kind == "project.field.create":
            self.service.create_project_field(action.payload)
        elif action.kind == "project.field.update_options":
            self.service.update_project_field_options(action.payload)
        elif action.kind == "repository.label.create":
            self.service.create_label(action.payload)
        elif action.kind == "project.view.create":
            self.service.create_project_view(action.payload)
        elif action.kind == "project.view.update":
            self.service.update_project_view(action.payload)
        else:
            raise ManifestError(f"Unsupported bootstrap action kind '{action.kind}'")


def apply_bootstrap_plan(
    plan: BootstrapPlan,
    *,
    executor: BootstrapExecutor,
    confirmation: str | None,
    discovery_snapshot: dict[str, Any] | None = None,
    journal: Journal | None = None,
) -> BootstrapResult:
    if not confirmation or confirmation != plan.digest:
        raise BootstrapAuthorizationError(
            "Bootstrap apply requires the exact reviewed plan digest"
        )
    if plan.digest != _plan_digest(
        plan.owner,
        plan.repository,
        plan.project_title,
        plan.requested_project_number,
        plan.project,
        plan.actions,
        plan.snapshot_fingerprint,
    ):
        raise BootstrapAuthorizationError("Bootstrap plan changed after validation")
    if discovery_snapshot is None:
        raise BootstrapAuthorizationError(
            "Bootstrap apply requires a freshly verified discovery snapshot"
        )
    fresh_plan = build_bootstrap_plan(
        plan.owner,
        plan.repository,
        discovery_snapshot,
        project_title=plan.project_title,
        project_number=plan.requested_project_number,
    )
    if fresh_plan.digest != plan.digest:
        raise BootstrapAuthorizationError(
            "Remote Project state drifted after review; rebuild and reconfirm the plan"
        )

    inputs_fingerprint = state_fingerprint(
        {
            "owner": plan.owner,
            "repository": plan.repository,
            "project_title": plan.project_title,
            "project_number": plan.requested_project_number,
        }
    )
    started_at = datetime.now(UTC).isoformat()
    completed: list[dict[str, Any]] = []
    current = receipt(
        plan.digest,
        inputs_fingerprint,
        plan.snapshot_fingerprint,
        "running",
        len(plan.actions),
        completed,
        started_at,
    )
    if journal:
        journal(current)
    if plan.project is not None:
        executor.select(plan.project)
    for action in plan.actions:
        try:
            executor(action)
        except Exception as exc:
            current = receipt(
                plan.digest,
                inputs_fingerprint,
                plan.snapshot_fingerprint,
                "failed",
                len(plan.actions),
                completed,
                started_at,
                failed_action=action.as_dict(),
                error=f"{type(exc).__name__}: {exc}",
            )
            if journal:
                journal(current)
            raise
        completed.append(action.as_dict())
        current = receipt(
            plan.digest,
            inputs_fingerprint,
            plan.snapshot_fingerprint,
            "running",
            len(plan.actions),
            completed,
            started_at,
        )
        if journal:
            journal(current)
    if executor.project is None:
        raise ManifestError("Bootstrap apply completed without a Project identity")
    current = receipt(
        plan.digest,
        inputs_fingerprint,
        plan.snapshot_fingerprint,
        "completed",
        len(plan.actions),
        completed,
        started_at,
    )
    if journal:
        journal(current)
    return BootstrapResult(executor.project, len(plan.actions), current)
