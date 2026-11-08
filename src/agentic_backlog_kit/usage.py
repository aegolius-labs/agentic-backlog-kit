"""Opt-in usage evidence (R37), per the organization's usage evidence contract.

https://github.com/aegolius-labs/.github/blob/main/docs/usage-evidence.md

Nothing is recorded in a project that has not run ``usage enable``. The ledger
is local, holds counts and command names only, and leaves the machine only
through ``usage publish`` to a repository the owner authorized in the config,
or through a person posting ``usage report --share`` themselves. Usage is
evidence about this kit, never intent: nothing here creates backlog items.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from . import __version__

USAGE_DIR = ".aegolius-usage"
CONFIG_FILE = "config.json"
EVENTS_FILE = "events.jsonl"
FEEDBACK_FILE = "feedback.jsonl"
KIT = "agentic-backlog-kit"

CONFIG_SCHEMA = "aegolius-usage-config/v1"
EVENT_SCHEMA = "aegolius-usage-event/v1"
FEEDBACK_SCHEMA = "aegolius-usage-feedback/v1"

KITS = (
    "aio-agentic-sdlc",
    "agentic-backlog-kit",
    "agentic-qa-kit",
    "agentic-product-playbook",
)
OUTCOMES = ("ok", "refused", "error")
HOSTS = ("claude-code", "codex", "antigravity", "unknown")
INITIATORS = ("person", "agent", "unknown")
SOURCES = ("agent-judgment", "person")
VERDICTS = ("helped", "neutral", "got_in_the_way")
MAX_FRICTION = 5
MAX_FRICTION_CHARS = 80
MIN_REPORTED_COUNT = 5

HOST_ENV = "AEGOLIUS_USAGE_HOST"
INITIATOR_ENV = "AEGOLIUS_USAGE_INITIATED_BY"
RUN_ID_ENV = "AEGOLIUS_USAGE_RUN_ID"

EVENT_FIELDS = (
    "schema",
    "ts",
    "kit",
    "kit_version",
    "command",
    "outcome",
    "error_class",
    "host",
    "initiated_by",
    "run_id",
)
FEEDBACK_FIELDS = ("schema", "ts", "kit", "run_id", "source", "verdict", "friction")
CONFIG_FIELDS = ("schema", "enabled", "enabled_at", "project_id", "publish")
PUBLISH_FIELDS = ("repository", "authorized_by", "authorized_at")

_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
_PROJECT_ID = re.compile(r"^u-[0-9a-f]{12}$")
_RUN_ID = re.compile(r"^r-[0-9a-f]{12}$")
_COMMAND = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_ERROR_CLASS = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")
# A friction phrase is a short description of friction, never project data.
_FORBIDDEN_PHRASE = (
    re.compile(r"[A-Za-z]:[\\/]"),  # Windows path
    re.compile(r"(^|[\s(])[~.]?/[\w.-]"),  # Unix path
    re.compile(r"\w[\\/]\w+\.\w{1,5}\b"),  # relative path to a file
    re.compile(r"\b[\w.-]+\.(py|js|ts|json|md|ya?ml|toml|txt|cfg)\b", re.I),
    re.compile(r"[a-z][a-z0-9+.-]*://", re.I),  # URL
    re.compile(r"\bwww\.", re.I),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),  # email
    re.compile(r"\b(gh[pousr]_|github_pat_|sk-|xox[abp]-|AKIA)[A-Za-z0-9_-]{6,}"),
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),  # long hex: a hash or key
    re.compile(r"\b[A-Za-z0-9+/_-]{40,}\b"),  # long opaque token
)


class UsageError(ValueError):
    """Raised when a usage command or record breaks the contract."""


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def usage_dir(root: str | Path) -> Path:
    return Path(root) / USAGE_DIR


def _exact_fields(record: Any, fields: Iterable[str], label: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise UsageError(f"{label} must be a JSON object")
    expected = set(fields)
    extra = sorted(set(record) - expected)
    missing = sorted(expected - set(record))
    if extra:
        raise UsageError(f"{label} carries fields the contract forbids: {', '.join(extra)}")
    if missing:
        raise UsageError(f"{label} is missing {', '.join(missing)}")
    return record


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise UsageError(message)


def _timestamp(value: Any, label: str) -> None:
    _require(isinstance(value, str) and bool(_TS.match(value)), f"{label} must be UTC ISO 8601 ending in Z")


def validate_config(config: Any) -> dict[str, Any]:
    _exact_fields(config, CONFIG_FIELDS, "usage config")
    _require(config["schema"] == CONFIG_SCHEMA, f"usage config schema must be {CONFIG_SCHEMA}")
    _require(isinstance(config["enabled"], bool), "usage config enabled must be a boolean")
    _timestamp(config["enabled_at"], "usage config enabled_at")
    _require(
        isinstance(config["project_id"], str) and bool(_PROJECT_ID.match(config["project_id"])),
        "usage config project_id must be u- followed by 12 hex digits",
    )
    publish = config["publish"]
    if publish is not None:
        _exact_fields(publish, PUBLISH_FIELDS, "usage config publish")
        _require(
            isinstance(publish["repository"], str) and bool(_REPOSITORY.match(publish["repository"])),
            "usage config publish.repository must be OWNER/REPO",
        )
        _require(
            isinstance(publish["authorized_by"], str) and publish["authorized_by"].strip() != "",
            "usage config publish.authorized_by must name the person who authorized it",
        )
        _timestamp(publish["authorized_at"], "usage config publish.authorized_at")
    return config


def validate_event(event: Any) -> dict[str, Any]:
    _exact_fields(event, EVENT_FIELDS, "usage event")
    _require(event["schema"] == EVENT_SCHEMA, f"usage event schema must be {EVENT_SCHEMA}")
    _timestamp(event["ts"], "usage event ts")
    _require(event["kit"] in KITS, "usage event kit is not an Aegolius Labs kit")
    _require(isinstance(event["kit_version"], str) and 0 < len(event["kit_version"]) <= 64, "usage event kit_version must be a short string")
    _require(
        isinstance(event["command"], str) and bool(_COMMAND.match(event["command"])),
        "usage event command must be a bare command name",
    )
    _require(event["outcome"] in OUTCOMES, "usage event outcome must be ok, refused or error")
    error_class = event["error_class"]
    _require(
        error_class is None or (isinstance(error_class, str) and bool(_ERROR_CLASS.match(error_class))),
        "usage event error_class must be a fixed code or null",
    )
    _require(event["host"] in HOSTS, "usage event host is not a known host")
    _require(event["initiated_by"] in INITIATORS, "usage event initiated_by must be person, agent or unknown")
    _require(
        isinstance(event["run_id"], str) and bool(_RUN_ID.match(event["run_id"])),
        "usage event run_id must be r- followed by 12 hex digits",
    )
    return event


def validate_friction(phrases: Any) -> list[str]:
    _require(isinstance(phrases, list), "friction must be a list")
    _require(len(phrases) <= MAX_FRICTION, f"friction holds at most {MAX_FRICTION} phrases")
    for phrase in phrases:
        _require(
            isinstance(phrase, str) and 0 < len(phrase.strip()) <= MAX_FRICTION_CHARS,
            f"each friction phrase must be 1 to {MAX_FRICTION_CHARS} characters",
        )
        for pattern in _FORBIDDEN_PHRASE:
            if pattern.search(phrase):
                raise UsageError(
                    "a friction phrase looks like a path, URL, email address or "
                    "secret; describe the friction without project data"
                )
    return phrases


def validate_feedback(feedback: Any) -> dict[str, Any]:
    _exact_fields(feedback, FEEDBACK_FIELDS, "usage feedback")
    _require(feedback["schema"] == FEEDBACK_SCHEMA, f"usage feedback schema must be {FEEDBACK_SCHEMA}")
    _timestamp(feedback["ts"], "usage feedback ts")
    _require(feedback["kit"] in KITS, "usage feedback kit is not an Aegolius Labs kit")
    run_id = feedback["run_id"]
    _require(
        run_id is None or (isinstance(run_id, str) and bool(_RUN_ID.match(run_id))),
        "usage feedback run_id must be r- followed by 12 hex digits, or null",
    )
    _require(feedback["source"] in SOURCES, "usage feedback source must be agent-judgment or person")
    _require(feedback["verdict"] in VERDICTS, "usage feedback verdict must be helped, neutral or got_in_the_way")
    validate_friction(feedback["friction"])
    return feedback


def load_config(root: str | Path) -> dict[str, Any] | None:
    path = usage_dir(root) / CONFIG_FILE
    if not path.is_file():
        return None
    return validate_config(json.loads(path.read_text(encoding="utf-8")))


def is_enabled(root: str | Path) -> bool:
    try:
        config = load_config(root)
    except (OSError, ValueError):
        return False
    return bool(config and config["enabled"])


def _write_config(root: str | Path, config: dict[str, Any]) -> None:
    validate_config(config)
    path = usage_dir(root) / CONFIG_FILE
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _ensure_gitignored(root: str | Path) -> bool:
    gitignore = Path(root) / ".gitignore"
    entry = f"{USAGE_DIR}/"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.is_file() else ""
    if any(line.strip() in {entry, USAGE_DIR, f"/{entry}", f"/{USAGE_DIR}"} for line in existing.splitlines()):
        return False
    separator = "" if not existing or existing.endswith("\n") else "\n"
    gitignore.write_text(f"{existing}{separator}{entry}\n", encoding="utf-8")
    return True


def enable(root: str | Path = ".") -> dict[str, Any]:
    folder = usage_dir(root)
    folder.mkdir(exist_ok=True)
    config = load_config(root)
    if config is None:
        config = {
            "schema": CONFIG_SCHEMA,
            "enabled": True,
            "enabled_at": utc_now(),
            "project_id": f"u-{secrets.token_hex(6)}",
            "publish": None,
        }
    elif not config["enabled"]:
        config = {**config, "enabled": True, "enabled_at": utc_now()}
    _write_config(root, config)
    gitignored = _ensure_gitignored(root)
    return {"enabled": True, "project_id": config["project_id"], "gitignore_updated": gitignored}


def disable(root: str | Path = ".") -> dict[str, Any]:
    config = load_config(root)
    if config is None:
        return {"enabled": False, "changed": False}
    changed = config["enabled"]
    if changed:
        _write_config(root, {**config, "enabled": False})
    return {"enabled": False, "changed": changed}


def purge(root: str | Path = ".") -> dict[str, Any]:
    folder = usage_dir(root)
    if folder.is_symlink():
        raise UsageError(f"{USAGE_DIR} is a symbolic link; refusing to delete through it")
    if not folder.exists():
        return {"purged": False}
    shutil.rmtree(folder)
    return {"purged": True}


def _append(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def current_host() -> str:
    explicit = os.environ.get(HOST_ENV, "")
    if explicit in HOSTS:
        return explicit
    # Only signals a host sets itself. Claude Code exports CLAUDECODE=1 to the
    # commands it runs; no equivalent is verified for the other hosts, so they
    # report unknown unless the host's own configuration sets HOST_ENV.
    if os.environ.get("CLAUDECODE") == "1":
        return "claude-code"
    return "unknown"


def current_initiator() -> str:
    value = os.environ.get(INITIATOR_ENV, "")
    return value if value in INITIATORS else "unknown"


_PROCESS_RUN_ID = f"r-{secrets.token_hex(6)}"


def current_run_id() -> str:
    value = os.environ.get(RUN_ID_ENV, "")
    return value if _RUN_ID.match(value) else _PROCESS_RUN_ID


def record_event(
    command: str,
    outcome: str,
    error_class: str | None = None,
    *,
    root: str | Path = ".",
) -> bool:
    """Append one event when the project opted in. Never raises."""

    try:
        if not is_enabled(root):
            return False
        event = validate_event(
            {
                "schema": EVENT_SCHEMA,
                "ts": utc_now(),
                "kit": KIT,
                "kit_version": __version__ or "unknown",
                "command": command,
                "outcome": outcome,
                "error_class": error_class,
                "host": current_host(),
                "initiated_by": current_initiator(),
                "run_id": current_run_id(),
            }
        )
        _append(usage_dir(root) / EVENTS_FILE, event)
        return True
    except (OSError, ValueError):
        return False


def add_feedback(
    verdict: str,
    *,
    source: str,
    friction: list[str] | None = None,
    run_id: str | None = None,
    root: str | Path = ".",
) -> dict[str, Any]:
    if not is_enabled(root):
        raise UsageError("usage recording is not enabled in this project; run `usage enable` first")
    feedback = validate_feedback(
        {
            "schema": FEEDBACK_SCHEMA,
            "ts": utc_now(),
            "kit": KIT,
            "run_id": run_id if run_id is not None else current_run_id(),
            "source": source,
            "verdict": verdict,
            "friction": [phrase.strip() for phrase in (friction or [])],
        }
    )
    _append(usage_dir(root) / FEEDBACK_FILE, feedback)
    return feedback


def _read_jsonl(path: Path, validate) -> tuple[list[dict[str, Any]], int]:
    if not path.is_file():
        return [], 0
    records, rejected = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(validate(json.loads(line)))
        except (ValueError, json.JSONDecodeError):
            rejected += 1
    return records, rejected


def _withheld(counter: Counter) -> dict[str, Any]:
    """Counts under the threshold are withheld, so a small group stays unread."""

    return {
        key: (count if count >= MIN_REPORTED_COUNT else f"<{MIN_REPORTED_COUNT}")
        for key, count in sorted(counter.items())
    }


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator < MIN_REPORTED_COUNT:
        return {"numerator": None, "denominator": None, "withheld": True}
    return {"numerator": numerator, "denominator": denominator, "withheld": False}


def build_report(roots: Iterable[str | Path]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    feedback: list[dict[str, Any]] = []
    rejected = 0
    projects = 0
    for root in roots:
        folder = usage_dir(root)
        if not folder.is_dir():
            continue
        projects += 1
        found, bad = _read_jsonl(folder / EVENTS_FILE, validate_event)
        events += found
        rejected += bad
        found, bad = _read_jsonl(folder / FEEDBACK_FILE, validate_feedback)
        feedback += found
        rejected += bad
    stamps = sorted(record["ts"] for record in events + feedback)
    friction = Counter(phrase for note in feedback for phrase in note["friction"])
    return {
        "schema": "aegolius-usage-report/v1",
        "projects": projects,
        "period": {"from": stamps[0], "to": stamps[-1]} if stamps else None,
        "events": len(events),
        "by_kit": _withheld(Counter(e["kit"] for e in events)),
        "by_command": _withheld(Counter(f"{e['kit']} {e['command']}" for e in events)),
        "by_outcome": _withheld(Counter(e["outcome"] for e in events)),
        "by_host": _withheld(Counter(e["host"] for e in events)),
        "by_initiator": _withheld(Counter(e["initiated_by"] for e in events)),
        "ok_rate": _rate(sum(e["outcome"] == "ok" for e in events), len(events)),
        "feedback": {
            source: _withheld(Counter(n["verdict"] for n in feedback if n["source"] == source))
            for source in SOURCES
        },
        "friction": {
            phrase: count for phrase, count in sorted(friction.items()) if count >= MIN_REPORTED_COUNT
        },
        "friction_withheld": sum(1 for count in friction.values() if count < MIN_REPORTED_COUNT),
        "rejected_lines": rejected,
    }


def _table(title: str, counts: dict[str, Any]) -> list[str]:
    if not counts:
        return [f"**{title}:** none", ""]
    lines = [f"**{title}**", "", "| Value | Count |", "| --- | --- |"]
    lines += [f"| {key} | {value} |" for key, value in counts.items()]
    return lines + [""]


def render_report_markdown(report: dict[str, Any]) -> str:
    period = report["period"]
    rate = report["ok_rate"]
    lines = [
        "## Kit usage summary",
        "",
        f"Projects: {report['projects']}. Events: {report['events']}."
        + (f" Period: {period['from']} to {period['to']}." if period else ""),
        f"Counts under {MIN_REPORTED_COUNT} are shown as <{MIN_REPORTED_COUNT}.",
        "",
        (
            "Commands that finished ok: withheld (fewer than "
            f"{MIN_REPORTED_COUNT} events)."
            if rate["withheld"]
            else f"Commands that finished ok: {rate['numerator']} of {rate['denominator']}."
        ),
        "",
    ]
    lines += _table("By kit", report["by_kit"])
    lines += _table("By command", report["by_command"])
    lines += _table("By outcome", report["by_outcome"])
    lines += _table("By host", report["by_host"])
    lines += _table("By initiator (self-reported)", report["by_initiator"])
    lines += _table("Feedback from people", report["feedback"]["person"])
    lines += _table(
        "Feedback by agent judgment (a model's opinion, not user evidence)",
        report["feedback"]["agent-judgment"],
    )
    lines += _table("Friction phrases", report["friction"])
    if report["friction_withheld"]:
        lines.append(f"{report['friction_withheld']} rarer friction phrase(s) withheld.")
    return "\n".join(lines).rstrip() + "\n"


def publish(root: str | Path, transport: Any) -> dict[str, Any]:
    """Post this project's summary to the owner-authorized repository."""

    config = load_config(root)
    if config is None:
        raise UsageError("usage recording was never enabled in this project")
    target = config["publish"]
    if target is None:
        raise UsageError(
            "usage publish needs the owner's recorded authorization: the project "
            "owner sets publish in .aegolius-usage/config.json themselves"
        )
    body = render_report_markdown(build_report([root]))
    repository = f"/repos/{target['repository']}"
    title = config["project_id"]
    number = None
    for page in range(1, 11):
        issues = transport.rest(
            "GET", f"{repository}/issues?state=all&per_page=100&page={page}"
        )
        for issue in issues or []:
            if issue.get("title") == title and "pull_request" not in issue:
                number = issue["number"]
                break
        if number is not None or not issues or len(issues) < 100:
            break
    created = number is None
    if created:
        issue = transport.rest(
            "POST",
            f"{repository}/issues",
            {"title": title, "body": "Usage summaries for one opted-in project."},
        )
        number = issue["number"]
    comment = transport.rest(
        "POST", f"{repository}/issues/{number}/comments", {"body": body}
    )
    return {
        "repository": target["repository"],
        "issue": number,
        "issue_created": created,
        "comment_url": comment.get("html_url"),
    }
