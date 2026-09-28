from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Iterable

from .execution import ApplyReceipt, Journal, failure_hint, receipt, state_fingerprint
from .manifest import ManifestError, canonical_guid, validate_manifest
from .priority import prioritize


class ApplyAuthorizationError(PermissionError):
    """Raised when apply is attempted without confirming the exact plan digest."""


@dataclass(frozen=True, slots=True)
class SyncAction:
    kind: str
    item_id: str
    payload: dict[str, Any]
    precondition: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "item_id": self.item_id,
            "payload": self.payload,
            "precondition": self.precondition,
        }


@dataclass(frozen=True, slots=True)
class SyncPlan:
    actions: list[SyncAction]
    digest: str
    manifest_fingerprint: str
    snapshot_fingerprint: str
    manage_body: bool = True
    transitions: dict[str, dict[str, Any]] = field(default_factory=dict)
    held_remote_edits: list[dict[str, Any]] = field(default_factory=list)
    overwrite_remote_edits: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "manifest_fingerprint": self.manifest_fingerprint,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "manage_body": self.manage_body,
            "transitions": self.transitions,
            "held_remote_edits": self.held_remote_edits,
            "overwrite_remote_edits": self.overwrite_remote_edits,
            "action_count": len(self.actions),
            "actions": [action.as_dict() for action in self.actions],
        }


MARKER_PREFIX = "<!-- agentic-backlog-kit:"
MARKER_SUFFIX = "-->"


def render_marker(item: dict[str, Any]) -> str:
    """Render the hidden marker, carrying the canonical GUID only when present.

    The GUID is appended after `schema=1` rather than bumping the marker schema:
    every reader since 0.1.0 takes the id only up to the first `;`, so existing
    issue bodies stay valid and none has to be rewritten. An older kit that
    rewrites a body regenerates the marker without the key; that is the one
    loss, and it is documented rather than engineered around.
    """

    marker = f"id={item['id']};schema=1"
    if item.get("guid"):
        marker += f";guid={item['guid']}"
    return f"{MARKER_PREFIX}{marker} {MARKER_SUFFIX}"


def _marker_span(body: str | None) -> tuple[int, int] | None:
    if not body:
        return None
    start = body.find(MARKER_PREFIX + "id=")
    if start < 0:
        return None
    end = body.find(MARKER_SUFFIX, start)
    if end < 0:
        return None
    return start, end + len(MARKER_SUFFIX)


def extract_marker_fields(body: str | None) -> dict[str, str]:
    """Return the marker's `key=value` pairs, or an empty mapping without one."""

    span = _marker_span(body)
    if span is None:
        return {}
    inner = body[span[0] + len(MARKER_PREFIX) : span[1] - len(MARKER_SUFFIX)]
    fields: dict[str, str] = {}
    for part in inner.strip().split(";"):
        key, separator, value = part.partition("=")
        if separator and key.strip() and key.strip() not in fields:
            fields[key.strip()] = value.strip()
    return fields


def extract_guid(body: str | None) -> str | None:
    """Return the marker's GUID when it is canonical, otherwise None.

    A non-canonical value is treated as absent rather than trusted, so the next
    plan proposes correcting it instead of projecting a second identity.
    """

    return canonical_guid(extract_marker_fields(body).get("guid"))


def with_marker(body: str, item: dict[str, Any]) -> str:
    """Replace only the marker, preserving every other character of the body."""

    span = _marker_span(body)
    if span is None:
        return f"{render_marker(item)}\n\n{body}" if body.strip() else render_marker(item)
    return body[: span[0]] + render_marker(item) + body[span[1] :]


WRITTEN_PREFIX = "<!-- agentic-backlog-kit:written="
WRITTEN_SUFFIX = " -->"
WRITTEN_VERSION = "v1"
_HEX16 = frozenset("0123456789abcdef")


def _canonical_text(text: str) -> str:
    """Normalize line endings and trailing whitespace for a stable digest.

    GitHub may normalize CRLF to LF (or the reverse, depending on how a body
    was written), so the digest has to be computed over a form that does not
    change under that normalization alone.
    """

    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip()


def _strip_written_comment(body: str | None) -> str:
    """Return the body's content with the trailing written-comment removed.

    The comment is always the last line the kit writes, so anything after it
    is preserved untouched (there should be nothing) while the comment itself,
    and the newline that separates it from the content, is dropped.
    """

    text = _canonical_text(body or "")
    start = text.rfind(WRITTEN_PREFIX)
    if start < 0:
        return text
    end = text.find(WRITTEN_SUFFIX, start)
    if end < 0:
        return text
    content = text[:start]
    trailing = text[end + len(WRITTEN_SUFFIX) :].strip()
    if content.endswith("\n"):
        content = content[:-1]
    if trailing:
        # Unexpected trailing content after the comment; keep it rather than
        # silently discard it.
        content = f"{content}\n{trailing}" if content else trailing
    return content


def compute_title_digest(title: str) -> str:
    """Return the first 16 hex characters of sha256(canonical title)."""

    return hashlib.sha256(_canonical_text(title).encode("utf-8")).hexdigest()[:16]


def compute_body_digest(content: str) -> str:
    """Return the first 16 hex characters of sha256(canonical content).

    `content` is the body with the written-comment already removed.
    """

    return hashlib.sha256(_canonical_text(content).encode("utf-8")).hexdigest()[:16]


def render_written_comment(title_digest: str, body_digest: str) -> str:
    return (
        f"{WRITTEN_PREFIX}{WRITTEN_VERSION};title={title_digest};body={body_digest}"
        f"{WRITTEN_SUFFIX}"
    )


def with_written_comment(title: str, body: str) -> str:
    """Return `body` with a fresh written-comment baseline appended.

    Both the title and body digests are computed fresh from exactly the
    (title, content) pair being written. Used for a brand-new issue, where
    there is no prior baseline to carry forward for either field.
    """

    content = _strip_written_comment(body)
    comment = render_written_comment(
        compute_title_digest(title), compute_body_digest(content)
    )
    return f"{content}\n{comment}" if content else comment


def _is_hex16(value: str) -> bool:
    return len(value) == 16 and all(char in _HEX16 for char in value)


def extract_written_digests(body: str | None) -> tuple[str | None, str | None]:
    """Return the written-comment's (title_digest, body_digest).

    Both come back `None` when the body carries no comment, an unknown
    version, or anything malformed: an unreadable baseline is treated exactly
    like an absent one, so the next write installs a fresh, readable one
    rather than planning against a comment it cannot trust.
    """

    if not body:
        return None, None
    start = body.rfind(WRITTEN_PREFIX)
    if start < 0:
        return None, None
    start += len(WRITTEN_PREFIX)
    end = body.find(WRITTEN_SUFFIX, start)
    if end < 0:
        return None, None
    inner = body[start:end].strip()
    parts = inner.split(";")
    if not parts or parts[0] != WRITTEN_VERSION:
        return None, None
    fields: dict[str, str] = {}
    for part in parts[1:]:
        key, separator, value = part.partition("=")
        if not separator:
            return None, None
        fields[key.strip()] = value.strip()
    title_digest = fields.get("title")
    body_digest = fields.get("body")
    if not title_digest or not body_digest:
        return None, None
    if not (_is_hex16(title_digest) and _is_hex16(body_digest)):
        return None, None
    return title_digest, body_digest


def render_issue_body(item: dict[str, Any]) -> str:
    criteria = "\n".join(
        f"- [ ] {criterion}" for criterion in item["acceptance_criteria"]
    )
    dependencies = ", ".join(item["depends_on"]) or "None"
    parent = item["parent"] or "None"
    return (
        f"{render_marker(item)}\n\n"
        f"## Outcome\n\n{item['description']}\n\n"
        f"## Acceptance criteria\n\n{criteria or '- [ ] Define acceptance criteria'}\n\n"
        "## Backlog metadata\n\n"
        f"- Type: {item['type']}\n"
        f"- Parent: {parent}\n"
        f"- Depends on: {dependencies}\n"
    )


def extract_item_id(body: str | None) -> str | None:
    marker = "<!-- agentic-backlog-kit:id="
    if not body or marker not in body:
        return None
    value = body.split(marker, 1)[1].split(";", 1)[0].strip()
    return value or None


def _desired_fields(
    item: dict[str, Any], priority_score: float, *, sprint_field: str
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "Status": item["status"],
        "Impact": item["impact"],
        "Effort": item["effort"],
        "Business Value": item["business_value"],
        "Enabler Value": item["enabler_value"],
        "Priority": priority_score,
    }
    if item.get("sprint"):
        if item["sprint"] in {"@current", "@next"}:
            raise ManifestError(
                f"Item '{item['id']}' sprint alias must be resolved to an exact "
                "active iteration title before synchronization"
            )
        fields[sprint_field] = item["sprint"]
    return fields


def operational_field_names(sprint_field: str) -> tuple[str, ...]:
    """Return the Project fields GitHub owns for work it already tracks.

    Status and the iteration field describe what is happening to an item now.
    That is an observation about reality, and reality is reported by GitHub, so
    the manifest supplies these only when an item is first projected.
    """

    return ("Status", sprint_field)


def _split_operational(
    fields: dict[str, Any], sprint_field: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    operational_names = operational_field_names(sprint_field)
    planning = {
        name: value
        for name, value in fields.items()
        if name not in operational_names
    }
    operational = {
        name: value for name, value in fields.items() if name in operational_names
    }
    return planning, operational


def normalize_transitions(
    transitions: dict[str, dict[str, Any]] | None,
    data: dict[str, Any],
    remote_by_id: dict[str, dict[str, Any]],
    sprint_field: str,
) -> dict[str, dict[str, Any]]:
    """Validate requested operational transitions before anything is planned.

    A transition is the only way local intent may move Status or Sprint for work
    GitHub already tracks, so every request is checked against the manifest's
    vocabulary and against the item actually existing remotely.
    """

    if not transitions:
        return {}
    statuses = set(data["workflow"]["statuses"])
    local_ids = {item["id"] for item in data["items"]}
    normalized: dict[str, dict[str, Any]] = {}
    for item_id in sorted(transitions):
        requested = transitions[item_id]
        if not isinstance(requested, dict) or not requested:
            raise ManifestError(
                f"Transition for '{item_id}' must name at least one operational field"
            )
        if item_id not in local_ids:
            raise ManifestError(f"Transition references unknown item '{item_id}'")
        remote = remote_by_id.get(item_id)
        if remote is None:
            raise ManifestError(
                f"Transition for '{item_id}' requires an existing GitHub issue; "
                "synchronize the item before transitioning it"
            )
        if not remote.get("in_project", False):
            raise ManifestError(
                f"Transition for '{item_id}' requires the item to be in the Project; "
                "synchronize the item before transitioning it"
            )
        allowed = operational_field_names(sprint_field)
        for name, value in sorted(requested.items()):
            if name not in allowed:
                raise ManifestError(
                    f"Transition for '{item_id}' may only set {', '.join(allowed)}; "
                    f"got '{name}'"
                )
            if name == "Status" and value not in statuses:
                raise ManifestError(
                    f"Transition for '{item_id}' status '{value}' is not one of the "
                    "manifest workflow statuses"
                )
            if value in {"@current", "@next"}:
                raise ManifestError(
                    f"Transition for '{item_id}' sprint alias must be resolved to an "
                    "exact active iteration title"
                )
        normalized[item_id] = dict(sorted(requested.items()))
    return normalized


def _normalize_remote(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("issues", []), list):
        raise ManifestError("Remote snapshot must contain an issues array")
    remote_by_id: dict[str, dict[str, Any]] = {}
    for index, issue in enumerate(snapshot.get("issues", [])):
        if not isinstance(issue, dict):
            raise ManifestError(f"Remote issue at index {index} must be an object")
        item_id = issue.get("abk_id") or extract_item_id(issue.get("body"))
        if not item_id:
            continue
        if item_id in remote_by_id:
            raise ManifestError(f"Remote snapshot contains duplicate ABK id '{item_id}'")
        remote_by_id[item_id] = issue
    return remote_by_id


def compose_operational_state(
    manifest: dict[str, Any], remote_snapshot: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the manifest with fresh GitHub operational state applied.

    Planning asks what should happen next, which depends on what is happening
    now.  What is happening now is an observation, and GitHub reports it, so
    ranking and sprint selection read Status and the iteration field from a
    fresh snapshot rather than from local intent.

    A remote status the manifest does not define is reported but not adopted:
    scoring and sprint rules are expressed in the manifest's vocabulary, and
    silently importing a foreign status would give those rules a value they
    cannot reason about.  Scaffolding appends the manifest's statuses to the
    ones GitHub already offers, so a board can legitimately carry statuses the
    manifest has never heard of.

    Returns the composed manifest and the list of observed differences.
    """

    data = validate_manifest(manifest)
    remote_by_id = _normalize_remote(remote_snapshot)
    iteration = data["workflow"].get("iteration") or {}
    sprint_field = iteration.get("field", "Sprint")
    statuses = set(data["workflow"]["statuses"])

    composed = deepcopy(data)
    differences: list[dict[str, Any]] = []
    for item in composed["items"]:
        remote = remote_by_id.get(item["id"])
        if remote is None or not remote.get("in_project", False):
            continue
        fields = remote.get("project_fields") or {}

        observed_status = fields.get("Status")
        if isinstance(observed_status, str) and observed_status != item["status"]:
            if observed_status in statuses:
                differences.append(
                    {
                        "id": item["id"],
                        "field": "status",
                        "local": item["status"],
                        "remote": observed_status,
                        "applied": True,
                    }
                )
                item["status"] = observed_status
            else:
                differences.append(
                    {
                        "id": item["id"],
                        "field": "status",
                        "local": item["status"],
                        "remote": observed_status,
                        "applied": False,
                        "reason": "remote status is not a manifest workflow status",
                    }
                )

        observed_sprint = fields.get(sprint_field)
        if isinstance(observed_sprint, str) and observed_sprint != item["sprint"]:
            differences.append(
                {
                    "id": item["id"],
                    "field": "sprint",
                    "local": item["sprint"],
                    "remote": observed_sprint,
                    "applied": True,
                }
            )
            item["sprint"] = observed_sprint

    return composed, differences


def _plan_digest(
    actions: Iterable[SyncAction],
    manifest_fingerprint: str,
    snapshot_fingerprint: str,
    manage_body: bool,
    transitions: dict[str, dict[str, Any]] | None = None,
    held_remote_edits: list[dict[str, Any]] | None = None,
    overwrite_remote_edits: list[str] | None = None,
) -> str:
    payload = {
        "actions": [action.as_dict() for action in actions],
        "manifest_fingerprint": manifest_fingerprint,
        "snapshot_fingerprint": snapshot_fingerprint,
        "manage_body": manage_body,
        "transitions": transitions or {},
        "held_remote_edits": held_remote_edits or [],
        "overwrite_remote_edits": overwrite_remote_edits or [],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_overwrite_remote_edits(
    overwrite_remote_edits: Iterable[str] | None,
    local_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    """Reject unknown items up front; whether each is actually held is checked

    per item during planning, since that depends on the remote snapshot.
    """

    ids = sorted({str(item_id) for item_id in (overwrite_remote_edits or ())})
    unknown = [item_id for item_id in ids if item_id not in local_by_id]
    if unknown:
        raise ManifestError(
            "--overwrite-remote-edit references unknown item(s): "
            + ", ".join(unknown)
        )
    return ids


def _issue_title_body_plan(
    item: dict[str, Any],
    remote: dict[str, Any],
    desired_body: str,
    *,
    manage_body: bool,
    overwrite: bool,
) -> tuple[dict[str, Any], list[str], bool]:
    """Return the title/body change, the fields still held, and whether any was held.

    Title and body each carry their own written-comment digest, so an edit to
    one is detected independently of the other. A field is held when GitHub's
    current digest for it no longer matches the digest the kit's last write
    recorded *and* the field now differs from what the manifest wants; a field
    that is unheld is planned as usual.

    A held field that is being kept (not overwritten) is *not* silently
    rewritten into a fresh baseline: whenever the body is rewritten for the
    other field's sake (for example, a title-only update still has to refresh
    the comment), a kept field's own digest is carried forward unchanged from
    whatever the remote's existing comment recorded. That keeps a still-held
    field detectably held on the next plan rather than laundering the human's
    edit into a new baseline the moment the *other* field is legitimately
    rewritten.

    A preserved body (`manage_body=False`) never holds its content - the kit
    only ever touches the identity marker there, never arbitrary prose - but
    its title is held on exactly the same terms as a managed body's.

    `overwrite` disables holding for this item: a held field is planned with
    the manifest's value regardless, which also lets its digest refresh.
    """

    remote_title = remote.get("title")
    remote_body = remote.get("body")
    remote_content = _strip_written_comment(remote_body)
    old_title_digest, old_body_digest = extract_written_digests(remote_body)
    current_title_digest = compute_title_digest(remote_title or "")
    current_body_digest = compute_body_digest(remote_content)

    title_differs = remote_title != item["title"]
    title_edited = (
        old_title_digest is not None and old_title_digest != current_title_digest
    )
    title_held = title_edited and title_differs

    if manage_body:
        candidate_content = _canonical_text(desired_body)
        body_differs = remote_content != candidate_content
        body_edited = (
            old_body_digest is not None and old_body_digest != current_body_digest
        )
        body_held = body_edited and body_differs
    else:
        # A preserved body still carries the kit's marker, so the GUID is
        # corrected in place without touching anything else in it - and only
        # when it is actually wrong, so an untouched issue whose GUID already
        # trivially matches (both absent) is not rewritten just to add a
        # marker it never had. This is never held: the kit isn't protecting a
        # human edit from its own arbitrary-content management, because it
        # does not do any.
        guid_mismatch = extract_guid(remote_body) != item.get("guid")
        candidate_content = (
            _canonical_text(with_marker(remote_content, item))
            if guid_mismatch
            else remote_content
        )
        body_held = False

    was_any_field_held = title_held or body_held
    effective_title_held = title_held and not overwrite
    effective_body_held = body_held and not overwrite

    final_title = remote_title if effective_title_held else item["title"]
    final_content = remote_content if effective_body_held else candidate_content

    title_changing = final_title != remote_title
    content_changing = final_content != remote_content

    issue_changes: dict[str, Any] = {}
    if title_changing:
        issue_changes["title"] = final_title

    # Only rewrite the body when the title or the content is actually
    # changing. A missing or stale written-comment baseline is not, on its
    # own, a reason to touch an issue that otherwise needs nothing: the kit
    # installs (or refreshes) the comment opportunistically, alongside a
    # write it was already making, rather than forcing one.
    if title_changing or content_changing:
        final_title_digest = (
            compute_title_digest(final_title)
            if title_changing
            else (
                old_title_digest if old_title_digest is not None else current_title_digest
            )
        )
        final_body_digest = (
            compute_body_digest(final_content)
            if content_changing
            else (
                old_body_digest if old_body_digest is not None else current_body_digest
            )
        )
        new_comment = render_written_comment(final_title_digest, final_body_digest)
        new_full_body = (
            f"{final_content}\n{new_comment}" if final_content else new_comment
        )
        if new_full_body != _canonical_text(remote_body or ""):
            issue_changes["body"] = new_full_body

    held_fields = (["title"] if effective_title_held else []) + (
        ["body"] if effective_body_held else []
    )
    return issue_changes, held_fields, was_any_field_held


def build_sync_plan(
    manifest: dict[str, Any],
    remote_snapshot: dict[str, Any],
    *,
    manage_body: bool = True,
    transitions: dict[str, dict[str, Any]] | None = None,
    overwrite_remote_edits: Iterable[str] | None = None,
) -> SyncPlan:
    """Build an idempotent local-to-GitHub plan without performing mutations.

    Ordinary synchronization never rewrites Status or the iteration field for
    work GitHub already tracks: those describe what is happening now, and
    GitHub observes that.  An item still receives the manifest's operational
    defaults the first time it is projected, and an explicit reviewed
    transition is the one way local intent may move them afterwards.

    A managed title or body is held back rather than planned when GitHub
    reports it changed since the kit's own last write: an agent confirming an
    ordinary plan must not be able to silently revert a human's edit.
    `overwrite_remote_edits` names items whose held edit the caller has
    reviewed and wants to overwrite with the manifest's version anyway; each
    must actually be held, or the request is rejected before anything is
    planned.
    """

    data = validate_manifest(manifest)
    remote_by_id = _normalize_remote(remote_snapshot)
    local_by_id = {item["id"]: item for item in data["items"]}
    iteration = data["workflow"].get("iteration") or {}
    sprint_field = iteration.get("field", "Sprint")
    requested_transitions = normalize_transitions(
        transitions, data, remote_by_id, sprint_field
    )
    normalized_overwrites = _normalize_overwrite_remote_edits(
        overwrite_remote_edits, local_by_id
    )
    overwrite_ids = set(normalized_overwrites)

    # Priority is a planning field derived from operational state, so it is
    # computed from fresh GitHub state with this plan's own transitions already
    # applied.  A plan should describe the state it intends to leave behind; if
    # it scored the state it found, every transition would need a second sync to
    # settle the priorities it just invalidated.
    operational, _ = compose_operational_state(manifest, remote_snapshot)
    intended = {item["id"]: item for item in operational["items"]}
    for item_id, fields in requested_transitions.items():
        target = intended.get(item_id)
        if target is None:  # pragma: no cover - rejected during normalization
            continue
        if "Status" in fields:
            target["status"] = fields["Status"]
        if sprint_field in fields:
            target["sprint"] = fields[sprint_field]
    score_by_id = {entry.id: entry.priority_score for entry in prioritize(operational)}

    creates: list[SyncAction] = []
    updates: list[SyncAction] = []
    project_actions: list[SyncAction] = []
    transition_actions: list[SyncAction] = []
    relationship_actions: list[SyncAction] = []
    held_remote_edits: list[dict[str, Any]] = []

    for item_id in sorted(local_by_id):
        item = local_by_id[item_id]
        remote = remote_by_id.get(item_id)
        desired_body = render_issue_body(item)
        desired_fields = _desired_fields(
            item, score_by_id[item_id], sprint_field=sprint_field
        )
        force_overwrite = item_id in overwrite_ids

        if remote is None:
            if force_overwrite:
                raise ManifestError(
                    f"--overwrite-remote-edit item '{item_id}' is not held for a "
                    "remote edit; it does not exist on GitHub yet"
                )
            creates.append(
                SyncAction(
                    "issue.create",
                    item_id,
                    {
                        "title": item["title"],
                        "body": with_written_comment(item["title"], desired_body),
                        "type": item["type"],
                        "fallback_label": f"type:{item['type'].lower()}",
                    },
                    {"issue": None},
                )
            )
            project_actions.append(
                SyncAction(
                    "project.add_item",
                    item_id,
                    {"fields": desired_fields},
                    {"issue": None, "requires": "issue.create"},
                )
            )
        else:
            issue_changes, held_fields, was_any_field_held = _issue_title_body_plan(
                item,
                remote,
                desired_body,
                manage_body=manage_body,
                overwrite=force_overwrite,
            )
            if force_overwrite and not was_any_field_held:
                raise ManifestError(
                    f"--overwrite-remote-edit item '{item_id}' is not held for a "
                    "remote edit"
                )
            if held_fields:
                held_remote_edits.append(
                    {
                        "item_id": item_id,
                        "issue_number": remote.get("number"),
                        "fields": held_fields,
                        "reason": "edited on GitHub since the kit last wrote it",
                        "hint": (
                            "Update the manifest item to accept the GitHub edit, "
                            f"or pass --overwrite-remote-edit {item_id} to restore "
                            "the manifest's version"
                        ),
                    }
                )
            if remote.get("type") != item["type"]:
                issue_changes["type"] = item["type"]
                fallback_label = f"type:{item['type'].lower()}"
                issue_changes["fallback_label"] = fallback_label
                if isinstance(remote.get("labels"), list):
                    unmanaged_labels = sorted(
                        {
                            label
                            for label in remote["labels"]
                            if isinstance(label, str)
                            and not label.casefold().startswith("type:")
                        }
                    )
                    issue_changes["labels"] = unmanaged_labels + [fallback_label]
            if issue_changes:
                updates.append(
                    SyncAction("issue.update", item_id, issue_changes, {"issue": remote})
                )

            if not remote.get("in_project", False):
                project_actions.append(
                    SyncAction(
                        "project.add_item",
                        item_id,
                        {"fields": desired_fields},
                        {"issue": remote},
                    )
                )
            else:
                current_fields = remote.get("project_fields") or {}
                planning_fields, _ = _split_operational(desired_fields, sprint_field)
                changed_fields = {
                    name: value
                    for name, value in planning_fields.items()
                    if current_fields.get(name) != value
                }
                if changed_fields:
                    project_actions.append(
                        SyncAction(
                            "project.set_fields",
                            item_id,
                            {"fields": changed_fields},
                            {"issue": remote},
                        )
                    )

                requested = requested_transitions.get(item_id)
                if requested:
                    changed_operational = {
                        name: value
                        for name, value in requested.items()
                        if current_fields.get(name) != value
                    }
                    if changed_operational:
                        transition_actions.append(
                            SyncAction(
                                "project.transition",
                                item_id,
                                {"fields": changed_operational},
                                {
                                    "issue": remote,
                                    "observed": {
                                        name: current_fields.get(name)
                                        for name in sorted(changed_operational)
                                    },
                                },
                            )
                        )

        current_parent = remote.get("parent_abk_id") if remote else None
        if item["parent"] and current_parent != item["parent"]:
            relationship_actions.append(
                SyncAction(
                    "issue.set_parent",
                    item_id,
                    {"parent": item["parent"]},
                    {"issue": remote},
                )
            )

        current_dependencies = set(
            remote.get("depends_on_abk_ids", []) if remote else []
        )
        for dependency in sorted(set(item["depends_on"]) - current_dependencies):
            relationship_actions.append(
                SyncAction(
                    "issue.add_dependency",
                    item_id,
                    {"depends_on": dependency},
                    {"issue": remote},
                )
            )

    actions = (
        creates
        + updates
        + project_actions
        + transition_actions
        + relationship_actions
    )
    held_remote_edits.sort(key=lambda entry: entry["item_id"])
    manifest_fingerprint = state_fingerprint(data)
    snapshot_fingerprint = state_fingerprint(remote_snapshot)
    return SyncPlan(
        actions=actions,
        digest=_plan_digest(
            actions,
            manifest_fingerprint,
            snapshot_fingerprint,
            manage_body,
            requested_transitions,
            held_remote_edits,
            normalized_overwrites,
        ),
        manifest_fingerprint=manifest_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
        manage_body=manage_body,
        transitions=requested_transitions,
        held_remote_edits=held_remote_edits,
        overwrite_remote_edits=normalized_overwrites,
    )


def apply_plan(
    plan: SyncPlan,
    *,
    executor: Callable[[SyncAction], Any],
    confirmation: str | None,
    manifest: dict[str, Any] | None = None,
    remote_snapshot: dict[str, Any] | None = None,
    journal: Journal | None = None,
) -> ApplyReceipt:
    """Execute only the exact plan the caller reviewed and confirmed."""

    if not confirmation or confirmation != plan.digest:
        raise ApplyAuthorizationError(
            "Apply requires the exact digest of the reviewed sync plan"
        )
    if _plan_digest(
        plan.actions,
        plan.manifest_fingerprint,
        plan.snapshot_fingerprint,
        plan.manage_body,
        plan.transitions,
        plan.held_remote_edits,
        plan.overwrite_remote_edits,
    ) != plan.digest:
        raise ApplyAuthorizationError("Sync plan changed after validation")
    if manifest is None or remote_snapshot is None:
        raise ApplyAuthorizationError(
            "Apply requires a freshly verified manifest and remote snapshot"
        )
    fresh_plan = build_sync_plan(
        manifest,
        remote_snapshot,
        manage_body=plan.manage_body,
        transitions=plan.transitions,
        overwrite_remote_edits=plan.overwrite_remote_edits,
    )
    if fresh_plan.digest != plan.digest:
        raise ApplyAuthorizationError(
            "Local or remote state drifted after review; rebuild and reconfirm the plan"
        )

    started_at = datetime.now(UTC).isoformat()
    completed: list[dict[str, Any]] = []
    current = receipt(
        plan.digest,
        plan.manifest_fingerprint,
        plan.snapshot_fingerprint,
        "running",
        len(plan.actions),
        completed,
        started_at,
    )
    if journal:
        journal(current)
    for action in plan.actions:
        try:
            executor(action)
        except Exception as exc:
            current = receipt(
                plan.digest,
                plan.manifest_fingerprint,
                plan.snapshot_fingerprint,
                "failed",
                len(plan.actions),
                completed,
                started_at,
                failed_action=action.as_dict(),
                error=f"{type(exc).__name__}: {exc}",
                hint=failure_hint(action.kind, action.payload, exc),
            )
            if journal:
                journal(current)
            raise
        completed.append(action.as_dict())
        current = receipt(
            plan.digest,
            plan.manifest_fingerprint,
            plan.snapshot_fingerprint,
            "running",
            len(plan.actions),
            completed,
            started_at,
        )
        if journal:
            journal(current)
    current = receipt(
        plan.digest,
        plan.manifest_fingerprint,
        plan.snapshot_fingerprint,
        "completed",
        len(plan.actions),
        completed,
        started_at,
    )
    if journal:
        journal(current)
    return current


def sync_plan_from_dict(data: dict[str, Any]) -> SyncPlan:
    if not isinstance(data, dict) or not isinstance(data.get("actions"), list):
        raise ManifestError("Sync plan must contain an actions array")
    actions: list[SyncAction] = []
    for index, raw in enumerate(data["actions"]):
        if not isinstance(raw, dict):
            raise ManifestError(f"Sync action at index {index} must be an object")
        kind = raw.get("kind")
        item_id = raw.get("item_id")
        payload = raw.get("payload")
        precondition = raw.get("precondition")
        if (
            not isinstance(kind, str)
            or not isinstance(item_id, str)
            or not isinstance(payload, dict)
            or not isinstance(precondition, dict)
        ):
            raise ManifestError(f"Sync action at index {index} is malformed")
        actions.append(SyncAction(kind, item_id, payload, precondition))
    digest = data.get("digest")
    manifest_fingerprint = data.get("manifest_fingerprint")
    snapshot_fingerprint = data.get("snapshot_fingerprint")
    manage_body = data.get("manage_body")
    transitions = data.get("transitions", {})
    if not isinstance(transitions, dict) or any(
        not isinstance(key, str) or not isinstance(value, dict)
        for key, value in transitions.items()
    ):
        raise ManifestError("Sync plan transitions must map item ids to field objects")
    held_remote_edits = data.get("held_remote_edits", [])
    if not isinstance(held_remote_edits, list) or any(
        not isinstance(entry, dict) for entry in held_remote_edits
    ):
        raise ManifestError("Sync plan held_remote_edits must be a list of objects")
    overwrite_remote_edits = data.get("overwrite_remote_edits", [])
    if not isinstance(overwrite_remote_edits, list) or any(
        not isinstance(entry, str) for entry in overwrite_remote_edits
    ):
        raise ManifestError("Sync plan overwrite_remote_edits must be a list of item ids")
    if (
        not isinstance(digest, str)
        or not isinstance(manifest_fingerprint, str)
        or not isinstance(snapshot_fingerprint, str)
        or not isinstance(manage_body, bool)
        or _plan_digest(
            actions,
            manifest_fingerprint,
            snapshot_fingerprint,
            manage_body,
            transitions,
            held_remote_edits,
            overwrite_remote_edits,
        )
        != digest
    ):
        raise ManifestError("Sync plan digest does not match its actions")
    return SyncPlan(
        actions=actions,
        digest=digest,
        manifest_fingerprint=manifest_fingerprint,
        snapshot_fingerprint=snapshot_fingerprint,
        manage_body=manage_body,
        transitions=transitions,
        held_remote_edits=held_remote_edits,
        overwrite_remote_edits=overwrite_remote_edits,
    )
