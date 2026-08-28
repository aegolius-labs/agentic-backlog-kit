from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .manifest import ManifestError, validate_manifest


TYPE_PREFIXES = {
    "Initiative": "INIT",
    "Epic": "EPIC",
    "Feature": "FEAT",
    "Story": "STORY",
    "Bug": "BUG",
    "Task": "TASK",
}


class StaleManifestError(RuntimeError):
    pass


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _next_id(data: dict[str, Any], item_type: str) -> str:
    prefix = TYPE_PREFIXES.get(item_type)
    if not prefix:
        raise ManifestError(f"Cannot generate an id for unknown item type '{item_type}'")
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    sequence = 0
    for item in data["items"]:
        match = pattern.fullmatch(item["id"])
        if match:
            sequence = max(sequence, int(match.group(1)))
    return f"{prefix}-{sequence + 1:04d}"


def add_item(
    manifest: dict[str, Any], draft: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    data = validate_manifest(manifest)
    if not isinstance(draft, dict):
        raise ManifestError("New backlog item must be an object")
    candidate = deepcopy(draft)
    item_id = candidate.get("id") or _next_id(data, candidate.get("type"))
    candidate["id"] = item_id
    data["items"].append(candidate)
    return validate_manifest(data), item_id


def update_item(
    manifest: dict[str, Any], item_id: str, patch: dict[str, Any]
) -> dict[str, Any]:
    data = validate_manifest(manifest)
    if not isinstance(patch, dict):
        raise ManifestError("Backlog item patch must be an object")
    if "id" in patch:
        raise ManifestError("Backlog item patch cannot change id")
    allowed = {
        "title",
        "type",
        "description",
        "acceptance_criteria",
        "parent",
        "depends_on",
        "impact",
        "effort",
        "business_value",
        "enabler_value",
        "status",
        "maturity",
        "sprint",
    }
    unknown = sorted(set(patch) - allowed)
    if unknown:
        raise ManifestError(f"Backlog item patch contains unknown fields: {unknown}")
    for item in data["items"]:
        if item["id"] == item_id:
            item.update(deepcopy(patch))
            return validate_manifest(data)
    raise ManifestError(f"Backlog item '{item_id}' was not found")


def save_manifest(
    path: str | Path,
    manifest: dict[str, Any],
    *,
    expected_sha256: str | None,
) -> str:
    """Atomically replace one expected manifest version under a short local lock."""

    target = Path(path)
    data = validate_manifest(manifest)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_suffix(target.suffix + ".lock")
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise StaleManifestError(f"Manifest is already being updated: {lock_path}") from exc
    try:
        os.close(lock_fd)
        current_hash = file_sha256(target) if target.exists() else None
        if current_hash != expected_sha256:
            raise StaleManifestError(
                f"Manifest changed: expected {expected_sha256}, found {current_hash}"
            )
        content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary_name = stream.name
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, target)
            temporary_name = None
        finally:
            if temporary_name and Path(temporary_name).exists():
                Path(temporary_name).unlink()
        return file_sha256(target)
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
