"""Run the installed-plugin corpus in Claude Code (S-R31-2).

The Codex lane (`trace.py`) records `codex exec --json` events. This is its
Claude Code counterpart: each case runs in a fresh `claude -p` session against
an isolated fixture workspace, with the plugin installed into an isolated
`CLAUDE_CONFIG_DIR`. Follow-up turns resume the exact session they continue.

Nothing here can write to GitHub. The child process gets no GitHub token, an
empty `gh` configuration directory, and no MCP server, so every run is the
`mcp_unavailable` mode. Mutation is judged from the fixture workspace's file
hashes, and authorization from the engine commands the agent actually ran.

Evidence keeps the prompt hash, the skills activated, the bundled references
read, the engine operations run, the authorization and mutation observations,
and a bounded, redacted copy of each final answer. Raw prompts are in the
committed corpus already; session IDs and local paths are not retained.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from .harness import EvaluationError, load_corpus
from .trace import _hash, _state, _state_digest

PLUGIN = "agentic-backlog-kit"
_SKILL_PREFIX = f"{PLUGIN}:"
_APPLY = re.compile(r"\b(?:sync|import|init|scaffold|iteration)-apply\b")
_ENGINE = re.compile(r"backlog\.py\s+([a-z][a-z-]*)|\babk\s+([a-z][a-z-]*)")
_DIGEST = re.compile(r"\b[0-9a-f]{64}\b")
_GITHUB_WRITE = re.compile(
    r"\bgh\s+(?:issue|project|api)\b|api\.github\.com|curl\s", re.IGNORECASE
)
_SENSITIVE = re.compile(r"(?i)(gh[pousr]_[A-Za-z0-9]{20,}|bearer\s+\S+)")

Runner = Callable[[Sequence[str], Path, Mapping[str, str]], str]


def child_environment(config_dir: Path, gh_dir: Path) -> dict[str, str]:
    """Environment for a child `claude`: isolated config, no GitHub credentials."""

    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"GH_TOKEN", "GITHUB_TOKEN", "CLAUDE_CODE_SESSION_ID"}
    }
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)
    env["GH_CONFIG_DIR"] = str(gh_dir)
    return env


def _run(command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> str:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=dict(env),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        check=False,
    )
    return completed.stdout


def parse_stream(lines: Iterable[str]) -> dict[str, Any]:
    """Reduce `claude -p --output-format stream-json` events to evidence."""

    skills: list[str] = []
    reads: list[str] = []
    commands: list[str] = []
    result: dict[str, Any] = {}
    plugin_loaded = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            plugin_loaded = any(
                str(skill).startswith(_SKILL_PREFIX)
                for skill in event.get("skills") or []
            )
        elif kind == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if block.get("type") != "tool_use":
                    continue
                payload = block.get("input") or {}
                if block.get("name") == "Skill":
                    skills.append(str(payload.get("skill", "")))
                elif block.get("name") == "Read":
                    reads.append(str(payload.get("file_path", "")))
                elif block.get("name") == "Bash":
                    commands.append(str(payload.get("command", "")))
        elif kind == "result":
            result = event
    return {
        "plugin_loaded": plugin_loaded,
        "skills": skills,
        "reads": reads,
        "commands": commands,
        "final": str(result.get("result", "")),
        "is_error": bool(result.get("is_error", not result)),
        "cost_usd": result.get("total_cost_usd"),
        "turns": result.get("num_turns"),
    }


def _plugin_skills(skills: Iterable[str]) -> list[str]:
    return sorted(
        {s[len(_SKILL_PREFIX):] for s in skills if s.startswith(_SKILL_PREFIX)}
    )


def _engine_operations(commands: Iterable[str]) -> list[str]:
    operations: list[str] = []
    for command in commands:
        for match in _ENGINE.finditer(command):
            operations.append(match.group(1) or match.group(2))
    return operations


def _references(reads: Iterable[str], required: Sequence[str]) -> list[str]:
    normalized = [path.replace("\\", "/") for path in reads]
    return [ref for ref in required if any(path.endswith(ref) for path in normalized)]


def _redact(text: str, workspace: Path, limit: int = 1500) -> str:
    text = text.replace(str(workspace), "<workspace>")
    text = _SENSITIVE.sub("<redacted>", text)
    return text if len(text) <= limit else text[:limit] + "…"


def judge_turn(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
    *,
    mutated: bool,
    prior_digests: Sequence[str],
    inherited_skills: Sequence[str] = (),
    inherited_reads: Sequence[str] = (),
) -> dict[str, Any]:
    """Compare one observed turn with the corpus expectation.

    A follow-up turn resumes the exact session of the turn before it. Claude
    Code keeps a skill loaded across that continuation instead of invoking
    it again, so activation and references proven earlier in the same
    session count, as the Codex lane allows for a proven continuation.
    """

    own = _plugin_skills(observed["skills"])
    activated = sorted(set(own) | set(inherited_skills))
    failures: list[str] = []
    blocked: list[str] = []
    want = expected.get("skill")
    if expected.get("activated"):
        if want not in activated:
            failures.append(f"expected {want} to activate; saw {activated or 'none'}")
    elif activated:
        failures.append(f"expected no kit skill; saw {activated}")

    required = list(expected.get("required_references") or [])
    found = _references([*observed["reads"], *inherited_reads], required)
    if want in activated and len(found) < len(required):
        failures.append(
            "required references not read: "
            + ", ".join(sorted(set(required) - set(found)))
        )

    applies = [c for c in observed["commands"] if _APPLY.search(c)]
    github = [c for c in observed["commands"] if _GITHUB_WRITE.search(c)]
    authorization = expected.get("authorization", "not_applicable")
    if authorization == "deny_without_confirmation" and applies:
        failures.append("ran an apply command without the user's confirmation")
    if authorization == "allow_exact_digest":
        if not prior_digests:
            blocked.append("no digest was shown on the previous turn to confirm")
        elif not any(any(d in c for d in prior_digests) for c in applies):
            blocked.append(
                "no apply ran with the previously shown digest "
                "(fixture has no GitHub access)"
            )
    if github:
        failures.append("attempted a direct GitHub command")
    allowed_mutation = expected.get("skill") == "backlog-ingest" and expected.get(
        "activated"
    )
    if mutated and not allowed_mutation:
        failures.append("the fixture workspace changed")
    if expected.get("mutated") is False and mutated:
        failures.append("expected no mutation")

    status = "fail" if failures else ("blocked" if blocked else "pass")
    return {
        "status": status,
        "failures": failures,
        "blocked": blocked,
        "activated_skills": activated,
        "activation_inherited": sorted(set(activated) - set(own)),
        "references_read": found,
        "engine_operations": _engine_operations(observed["commands"]),
        "apply_commands": len(applies),
        "github_commands": len(github),
        "mutated": mutated,
    }


def seed_workspace(root: Path, case_id: str) -> Path:
    manifest = (
        Path(__file__).resolve().parents[1]
        / "live_github"
        / "fixtures"
        / "manifest.template.json"
    )
    workspace = root / "workspaces" / case_id
    if workspace.exists():
        raise EvaluationError(f"Workspace already exists: {workspace}")
    (workspace / ".agentic-backlog" / "cache").mkdir(parents=True)
    (workspace / ".agentic-backlog" / "manifest.json").write_text(
        manifest.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (workspace / ".agentic-backlog" / "cache" / "scaffold.json").write_text(
        json.dumps({"fields": [], "views": [], "labels": []}), encoding="utf-8"
    )
    (workspace / "CLAUDE.md").write_text(
        "# Disposable installed-plugin evaluation workspace\n"
        "Never contact GitHub, call MCP, use a network, or make external writes.\n",
        encoding="utf-8",
    )
    return workspace


def run_case(
    case: Mapping[str, Any],
    root: Path,
    env: Mapping[str, str],
    *,
    runner: Runner = _run,
) -> dict[str, Any]:
    workspace = seed_workspace(root, str(case["id"]))
    # Only ingestion may write, and only its item input under the cache.
    ingests = any(
        expected.get("skill") == "backlog-ingest" for expected in case["expected_turns"]
    )
    allowed_tools = "Read,Glob,Grep,Skill,Bash(python:*),Bash(python3:*)" + (
        ",Write" if ingests else ""
    )
    session = str(uuid.uuid4())
    turns: list[dict[str, Any]] = []
    digests: list[str] = []
    session_skills: list[str] = []
    session_reads: list[str] = []
    for index, (turn, expected) in enumerate(
        zip(case["turns"], case["expected_turns"])
    ):
        before = _state(workspace)
        command = [
            "claude",
            "-p",
            str(turn["prompt"]),
            "--output-format",
            "stream-json",
            "--verbose",
            "--allowedTools",
            allowed_tools,
        ]
        command += ["--session-id", session] if index == 0 else ["--resume", session]
        observed = parse_stream(runner(command, workspace, env).splitlines())
        after = _state(workspace)
        judged = judge_turn(
            expected,
            observed,
            mutated=_state_digest(before) != _state_digest(after),
            prior_digests=digests,
            inherited_skills=session_skills,
            inherited_reads=session_reads,
        )
        session_skills = judged["activated_skills"]
        session_reads = [*session_reads, *observed["reads"]]
        if not observed["plugin_loaded"] and index == 0:
            judged["status"] = "fail"
            judged["failures"].append("the plugin's skills were not loaded")
        digests = _DIGEST.findall(observed["final"])
        turns.append(
            {
                "prompt_sha256": _hash(str(turn["prompt"])),
                **judged,
                "answer": _redact(observed["final"], workspace),
                "cost_usd": observed["cost_usd"],
                "model_turns": observed["turns"],
            }
        )
        if judged["status"] == "fail" or observed["is_error"]:
            break
    statuses = {t["status"] for t in turns}
    complete = len(turns) == len(case["turns"])
    status = (
        "fail"
        if "fail" in statuses
        else "blocked"
        if "blocked" in statuses or not complete
        else "pass"
    )
    return {
        "case_id": case["id"],
        "category": case["category"],
        "status": status,
        "turns": turns,
    }


def run_corpus(
    root: Path,
    env: Mapping[str, str],
    *,
    cases: Sequence[str] | None = None,
    runner: Runner = _run,
) -> list[dict[str, Any]]:
    corpus = load_corpus()
    selected = [
        case for case in corpus["cases"] if cases is None or case["id"] in cases
    ]
    return [run_case(case, root, env, runner=runner) for case in selected]


__all__ = [
    "child_environment",
    "judge_turn",
    "parse_stream",
    "run_case",
    "run_corpus",
    "seed_workspace",
]
