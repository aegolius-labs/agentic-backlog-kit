from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Callable, Mapping, Sequence


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[1]
CORPUS_PATH = HERE / "fixtures" / "evaluation-corpus.json"
PLUGIN_NAME = "agentic-backlog-kit"
PROMPT_CATEGORIES = (
    "direct",
    "indirect",
    "follow_up",
    "negative",
    "boundary",
    "write_confirmation",
)
EXECUTOR_MODES = ("mcp_available", "mcp_unavailable")
EXPECTED_SKILLS = (
    "backlog-init",
    "backlog-ingest",
    "backlog-prioritize",
    "backlog-sprint-plan",
    "backlog-sync-github",
)
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
FRONTMATTER_DELIMITER = "---"
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SECRET_PATTERN = re.compile(
    r"(?i)(?:authorization|bearer|gh_token|github_token|openai_api_key|api_key)"
    r"\s*[:=]\s*[^\s,;]+"
)
SECRET_ENVIRONMENT_KEYS = {
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "ANTHROPIC_API_KEY",
}


class EvaluationError(ValueError):
    """Raised when an evaluation artifact cannot be prepared safely."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"Cannot read JSON from {path}: {exc}") from exc


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        raise EvaluationError(f"{path}: missing YAML frontmatter")
    try:
        end = lines.index(FRONTMATTER_DELIMITER, 1)
    except ValueError as exc:
        raise EvaluationError(f"{path}: unterminated YAML frontmatter") from exc
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def _relative_links(skill_file: Path) -> list[str]:
    links: list[str] = []
    for raw in LINK_PATTERN.findall(skill_file.read_text(encoding="utf-8")):
        target = raw.strip().strip("<>").split("#", 1)[0].split("?", 1)[0]
        if not target or re.match(r"^[a-z][a-z0-9+.-]*://", target, re.I):
            continue
        links.append(target)
    return links


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, Any]:
    """Load and validate the checked-in prompt corpus."""

    corpus = _read_json(path)
    if not isinstance(corpus, dict):
        raise EvaluationError("The evaluation corpus must be a JSON object")
    if corpus.get("schema_version") != 1:
        raise EvaluationError("The evaluation corpus schema_version must be 1")
    if corpus.get("plugin") != PLUGIN_NAME:
        raise EvaluationError("The evaluation corpus targets an unexpected plugin")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EvaluationError("The evaluation corpus must contain cases")
    seen: set[str] = set()
    categories: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise EvaluationError("Every evaluation case must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise EvaluationError(f"Evaluation case IDs must be unique: {case_id!r}")
        seen.add(case_id)
        category = case.get("category")
        if category not in PROMPT_CATEGORIES:
            raise EvaluationError(f"Unsupported evaluation category: {category!r}")
        categories.add(category)
        if case.get("fresh_task") is not True:
            raise EvaluationError(f"{case_id}: every case must start a fresh task")
        turns = case.get("turns")
        expected = case.get("expected_turns")
        if (
            not isinstance(turns, list)
            or not turns
            or not isinstance(expected, list)
            or len(turns) != len(expected)
        ):
            raise EvaluationError(f"{case_id}: turns and expected_turns must align")
        for turn in turns:
            if not isinstance(turn, dict) or not isinstance(turn.get("prompt"), str):
                raise EvaluationError(f"{case_id}: every turn needs a prompt")
        for expectation in expected:
            if not isinstance(expectation, dict):
                raise EvaluationError(f"{case_id}: expected turn must be an object")
            if not isinstance(expectation.get("activated"), bool):
                raise EvaluationError(f"{case_id}: expected activated must be boolean")
            skill = expectation.get("skill")
            if skill is not None and skill not in EXPECTED_SKILLS:
                raise EvaluationError(f"{case_id}: unexpected expected skill {skill!r}")
    missing = set(PROMPT_CATEGORIES) - categories
    if missing:
        raise EvaluationError(
            "The evaluation corpus is missing categories: " + ", ".join(sorted(missing))
        )
    return copy.deepcopy(corpus)


def _manifest_path(plugin_root: Path) -> Path:
    return plugin_root / ".codex-plugin" / "plugin.json"


def inspect_installation(plugin_root: Path) -> dict[str, Any]:
    """Check the files Codex should pick up after local installation.

    This is deliberately static. It does not read or write a user marketplace,
    start Codex, contact GitHub, or infer that a conversation activated a skill.
    """

    root = Path(plugin_root).resolve()
    failures: list[str] = []
    missing_references: list[str] = []
    references_checked: list[str] = []
    skills: list[str] = []
    manifest_data: dict[str, Any] = {}
    manifest = _manifest_path(root)
    if not manifest.is_file():
        return {
            "passed": False,
            "failures": ["missing .codex-plugin/plugin.json"],
            "missing_references": [],
            "references_checked": [],
            "skills": [],
            "skill_count": 0,
            "manifest": {"path_valid": False, "skills_path_valid": False},
        }
    try:
        loaded = _read_json(manifest)
        if not isinstance(loaded, dict):
            raise EvaluationError("plugin.json must contain an object")
        manifest_data = loaded
    except EvaluationError as exc:
        failures.append(str(exc))

    if manifest_data.get("name") != PLUGIN_NAME:
        failures.append(
            f"plugin manifest name is {manifest_data.get('name')!r}; expected {PLUGIN_NAME!r}"
        )
    skills_value = manifest_data.get("skills")
    skills_path_valid = (
        isinstance(skills_value, str)
        and skills_value.startswith("./")
        and not Path(skills_value).is_absolute()
    )
    skills_root = root / skills_value[2:] if skills_path_valid else root / "skills"
    if not skills_path_valid:
        failures.append("plugin manifest skills must be a relative ./ path")
    if not _is_within(skills_root, root) or not skills_root.is_dir():
        failures.append("plugin manifest skills path is missing or escapes the plugin")
    else:
        for directory in sorted(skills_root.iterdir(), key=lambda item: item.name):
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            skills.append(directory.name)
            skill_file = directory / "SKILL.md"
            metadata_file = directory / "agents" / "openai.yaml"
            if not skill_file.is_file():
                failures.append(f"skill {directory.name} is missing SKILL.md")
                continue
            if not metadata_file.is_file() or not metadata_file.read_text(
                encoding="utf-8"
            ).strip():
                failures.append(f"skill {directory.name} is missing agents/openai.yaml")
            try:
                frontmatter = _parse_frontmatter(skill_file)
            except (OSError, EvaluationError) as exc:
                failures.append(str(exc))
                frontmatter = {}
            if frontmatter.get("name") != directory.name:
                failures.append(
                    f"skill {directory.name} frontmatter name is {frontmatter.get('name')!r}"
                )
            if not frontmatter.get("description"):
                failures.append(f"skill {directory.name} has no description")
            for target in _relative_links(skill_file):
                resolved = (skill_file.parent / target).resolve()
                relative_target = (
                    _relative(resolved, root) if _is_within(resolved, root) else target
                )
                references_checked.append(relative_target.replace("\\", "/"))
                if not _is_within(resolved, directory):
                    failures.append(
                        f"skill {directory.name} reference {target!r} escapes the skill"
                    )
                elif not resolved.is_file():
                    missing_references.append(relative_target.replace("\\", "/"))
                    failures.append(
                        f"skill {directory.name} reference {target!r} is missing"
                    )
    expected_missing = sorted(set(EXPECTED_SKILLS) - set(skills))
    failures.extend(f"missing expected skill {name}" for name in expected_missing)
    return {
        "passed": not failures,
        "failures": failures,
        "missing_references": sorted(set(missing_references)),
        "references_checked": sorted(set(references_checked)),
        "skills": skills,
        "skill_count": len(skills),
        "manifest": {
            "name": manifest_data.get("name"),
            "version": manifest_data.get("version"),
            "skills_path": skills_value,
            "path_valid": manifest.is_file(),
            "skills_path_valid": skills_path_valid and _is_within(skills_root, root),
            "sha256": _sha256_file(manifest),
        },
    }


def _marketplace_check(
    marketplace_path: Path, *, workspace_root: Path, plugin_name: str = PLUGIN_NAME
) -> dict[str, Any]:
    failures: list[str] = []
    try:
        marketplace = _read_json(marketplace_path)
    except EvaluationError as exc:
        return {"passed": False, "failures": [str(exc)], "source_resolves": False}
    if not isinstance(marketplace, dict):
        return {
            "passed": False,
            "failures": ["marketplace must contain an object"],
            "source_resolves": False,
        }
    plugins = marketplace.get("plugins")
    entry = next(
        (value for value in plugins if isinstance(value, dict) and value.get("name") == plugin_name),
        None,
    ) if isinstance(plugins, list) else None
    if entry is None:
        failures.append(f"marketplace has no {plugin_name} entry")
        return {"passed": False, "failures": failures, "source_resolves": False}
    source = entry.get("source")
    source_path = source.get("path") if isinstance(source, dict) else None
    if not isinstance(source, dict) or source.get("source") != "local":
        failures.append("marketplace plugin source must be local")
    if not isinstance(source_path, str) or not source_path.startswith("./"):
        failures.append("marketplace plugin source path must be a relative ./ path")
        source_target = workspace_root / "missing"
    else:
        source_target = (workspace_root / source_path[2:]).resolve()
        if not _is_within(source_target, workspace_root):
            failures.append("marketplace source path escapes the workspace")
    policy = entry.get("policy")
    if not isinstance(policy, dict):
        failures.append("marketplace plugin policy is missing")
    else:
        if policy.get("installation") != "AVAILABLE":
            failures.append("marketplace installation policy must be AVAILABLE")
        if policy.get("authentication") != "ON_INSTALL":
            failures.append("marketplace authentication policy must be ON_INSTALL")
    source_resolves = _manifest_path(source_target).is_file()
    if not source_resolves:
        failures.append("marketplace source does not resolve to a plugin manifest")
    return {
        "passed": not failures,
        "failures": failures,
        "source_resolves": source_resolves,
        "source_path": source_path,
        "plugin_name": entry.get("name"),
    }


def _copy_plugin(source: Path, destination: Path) -> None:
    ignored_names = {
        ".git",
        ".worktrees",
        ".agents",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
    }
    source = source.resolve()
    destination = destination.resolve()

    def ignore(current: str, names: list[str]) -> set[str]:
        excluded: set[str] = set()
        current_path = Path(current).resolve()
        for name in names:
            if name in ignored_names:
                excluded.add(name)
                continue
            # The requested output is often inside the checkout (for example
            # under .agentic-backlog/). Exclude that exact destination so a
            # rerun cannot recursively copy its own staged workspace.
            if (current_path / name).resolve() == destination:
                excluded.add(name)
        return excluded

    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)


def prepare_suite(
    output_root: Path,
    *,
    run_id: str = "r06-local",
    plugin_root: Path | None = None,
) -> dict[str, Any]:
    """Prepare a deterministic local marketplace and fresh-task corpus.

    All generated files live below ``output_root``. The function never edits a
    personal marketplace and never invokes a model or a network transport.
    """

    if not isinstance(run_id, str) or not run_id.strip():
        raise EvaluationError("run_id must be a non-empty string")
    root = Path(plugin_root or REPOSITORY_ROOT).resolve()
    output = Path(output_root).resolve()
    inspection = inspect_installation(root)
    if not inspection["passed"]:
        raise EvaluationError(
            "Cannot prepare an installation with static pickup failures: "
            + "; ".join(inspection["failures"])
        )
    corpus = load_corpus()
    output.mkdir(parents=True, exist_ok=True)
    workspace = output / "workspace"
    staged = workspace / "plugins" / PLUGIN_NAME
    _copy_plugin(root, staged)
    marketplace_path = workspace / ".agents" / "plugins" / "marketplace.json"
    marketplace = {
        "name": "r06-local",
        "interface": {"displayName": "R06 Local Evaluation"},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Developer Tools",
            }
        ],
    }
    _write_json(marketplace_path, marketplace)
    corpus_output = output / "fixtures" / "evaluation-corpus.json"
    _write_json(corpus_output, corpus)
    artifacts = {
        "workspace": "workspace",
        "marketplace": "workspace/.agents/plugins/marketplace.json",
        "staged_plugin": f"workspace/plugins/{PLUGIN_NAME}",
        "corpus": "fixtures/evaluation-corpus.json",
        "results": "results.ndjson",
        "diagnostics": "diagnostics.json",
        "report": "report.json",
    }
    plugin_manifest = _manifest_path(staged)
    suite_base: dict[str, Any] = {
        "schema_version": 1,
        "suite": corpus["suite"],
        "run_id": run_id,
        "plugin": {
            "name": PLUGIN_NAME,
            "version": inspection["manifest"].get("version"),
            "manifest_sha256": _sha256_file(plugin_manifest),
        },
        "fresh_task_required": True,
        "categories": list(PROMPT_CATEGORIES),
        "executor_matrix": [
            {
                "id": "mcp_available",
                "github_mcp": "available",
                "expected_transport": "github-mcp",
            },
            {
                "id": "mcp_unavailable",
                "github_mcp": "unavailable",
                "expected_transport": "cli-or-api-fallback",
            },
        ],
        "cases": corpus["cases"],
        "corpus": {
            "path": artifacts["corpus"],
            "sha256": _sha256_file(corpus_output),
        },
        "artifacts": artifacts,
        "marketplace": {
            "path": artifacts["marketplace"],
            "source_path": f"./plugins/{PLUGIN_NAME}",
            "source_resolves": True,
        },
        "authorization_contract": {
            "write_requests_require_exact_reviewed_digest": True,
            "no_confirmation_may_mutate": False,
            "record_confirmation_and_mutation_separately": True,
        },
        "result_contract": {
            "one_record_per_case": True,
            "prompt_sha256_required": True,
            "fresh_task_required": True,
            "retain_activation_and_skill": True,
            "retain_references_and_confirmation": True,
            "redact_credentials": True,
            "executor_runs_required": True,
            "executor_modes": list(EXECUTOR_MODES),
        },
        "static_pickup": inspection,
        "status": "prepared",
        "fresh_task_execution_required": True,
    }
    suite = {
        **suite_base,
        "suite_digest": _digest(suite_base),
    }
    _write_json(output / "suite.json", suite)
    return copy.deepcopy(suite)


def _safe_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in SECRET_ENVIRONMENT_KEYS:
        environment.pop(key, None)
    return environment


def _redact_output(value: Any) -> str:
    text = str(value or "")
    return SECRET_PATTERN.sub("<redacted>", text)[:4000]


def _contains_secret_like_text(value: Any) -> bool:
    if isinstance(value, str):
        return SECRET_PATTERN.search(value) is not None
    if isinstance(value, Mapping):
        return any(_contains_secret_like_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_secret_like_text(item) for item in value)
    return False


def probe_codex_cli(
    *,
    executable: str | Path | None = None,
    runner: Callable[..., Any] | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Attempt only non-mutating ``--help`` and ``--version`` probes."""

    process_runner = runner or subprocess.run
    candidate = str(executable) if executable is not None else shutil.which("codex")
    if not candidate:
        candidate = shutil.which("codex.exe")
    if not candidate:
        return {
            "status": "unavailable",
            "reason": "Codex CLI executable was not found on PATH",
            "commands": [],
            "credential_material_recorded": False,
        }
    commands: list[dict[str, Any]] = []
    for argument in ("--help", "--version"):
        command = [candidate, argument]
        try:
            completed = process_runner(
                command,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=15,
                env=_safe_environment(),
            )
        except Exception as exc:  # noqa: BLE001 - diagnostics must never abort the suite
            reason = _redact_output(exc)
            return {
                "status": "blocked",
                "reason": reason,
                "executable": Path(candidate).name,
                "commands": commands,
                "credential_material_recorded": False,
            }
        return_code = getattr(completed, "returncode", None)
        commands.append(
            {
                "args": [argument],
                "returncode": return_code,
                "stdout": _redact_output(getattr(completed, "stdout", "")),
                "stderr": _redact_output(getattr(completed, "stderr", "")),
            }
        )
        if return_code != 0:
            return {
                "status": "failed",
                "reason": f"Codex CLI {argument} probe returned {return_code}",
                "executable": Path(candidate).name,
                "commands": commands,
                "credential_material_recorded": False,
            }
    return {
        "status": "passed",
        "reason": "Read-only Codex CLI help and version probes completed",
        "executable": Path(candidate).name,
        "commands": commands,
        "credential_material_recorded": False,
    }


def run_diagnostics(
    suite: Mapping[str, Any],
    *,
    suite_root: Path | None = None,
    run_cli: bool = False,
    executable: str | Path | None = None,
) -> dict[str, Any]:
    """Run static pickup checks and, only when requested, safe CLI probes."""

    root = Path(suite_root or ".").resolve()
    artifacts = suite.get("artifacts", {})
    workspace = root / str(artifacts.get("workspace", "workspace"))
    staged = root / str(artifacts.get("staged_plugin", "workspace/plugins/agentic-backlog-kit"))
    marketplace = root / str(
        artifacts.get("marketplace", "workspace/.agents/plugins/marketplace.json")
    )
    static = inspect_installation(staged)
    market = _marketplace_check(marketplace, workspace_root=workspace)
    cli = (
        probe_codex_cli(executable=executable, cwd=workspace)
        if run_cli
        else {
            "status": "not_run",
            "reason": "CLI probes are opt-in because they start a local executable",
            "commands": [],
            "credential_material_recorded": False,
        }
    )
    static_passed = bool(static.get("passed") and market.get("passed"))
    cli_passed = not run_cli or cli.get("status") == "passed"
    return {
        "schema_version": 1,
        "suite": suite.get("suite"),
        "static_pickup": static,
        "marketplace": market,
        "codex_cli": cli,
        "passed": bool(static_passed and cli_passed),
        "static_passed": static_passed,
        "cli_probe_required": run_cli,
        "fresh_task_ready": bool(static_passed and cli_passed),
        "credential_material_recorded": False,
    }


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def synthetic_results(suite: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Create deterministic schema-valid records for verifier tests.

    These records prove the harness contract only. They are never presented as
    evidence that Codex installed or activated the plugin.
    """

    results: list[dict[str, Any]] = []
    plugin_name = str(suite.get("plugin", {}).get("name", PLUGIN_NAME))
    for case in suite.get("cases", []):
        turns: list[dict[str, Any]] = []
        expected_turns = case.get("expected_turns", [])
        for turn, expected in zip(case.get("turns", []), expected_turns):
            active = bool(expected.get("activated"))
            expected_auth = expected.get("authorization")
            requires_confirmation = bool(expected.get("requires_confirmation"))
            allowed = expected_auth == "allow_exact_digest"
            plan_digest = "a" * 64 if requires_confirmation or allowed else None
            provided = allowed
            confirmation = {
                "requested": requires_confirmation,
                "provided": provided,
                "plan_digest": plan_digest,
                "confirmed_digest": plan_digest if provided else None,
            }
            authorization = {
                "decision": "allowed" if allowed else ("denied" if requires_confirmation else "not_applicable"),
                "mutated": False,
            }
            turns.append(
                {
                    "prompt": turn["prompt"],
                    "prompt_sha256": _prompt_hash(turn["prompt"]),
                    "activated": active,
                    "plugin": plugin_name if active else None,
                    "skill": expected.get("skill") if active else None,
                    "references": list(expected.get("required_references", [])),
                    "references_resolved": True,
                    "confirmation": confirmation,
                    "authorization": authorization,
                    "identifier_reused": bool(expected.get("requires_prior_identifier")),
                    "tool_calls": [] if not active else [
                        {"skill": expected.get("skill"), "mutating": False}
                    ],
                }
            )
        remote_skill = any(
            expected.get("skill") in {"backlog-init", "backlog-sprint-plan", "backlog-sync-github"}
            for expected in expected_turns
            if isinstance(expected, Mapping)
        )
        active = any(
            expected.get("activated") is True
            for expected in expected_turns
            if isinstance(expected, Mapping)
        )
        executor_runs = []
        for mode in EXECUTOR_MODES:
            if not active:
                transport = "none"
                fallback_used = False
            elif not remote_skill:
                transport = "local-engine"
                fallback_used = False
            elif mode == "mcp_available":
                transport = "github-mcp"
                fallback_used = False
            else:
                transport = "cli-or-api-fallback"
                fallback_used = True
            executor_runs.append(
                {
                    "mode": mode,
                    "github_mcp": "available" if mode == "mcp_available" else "unavailable",
                    "transport": transport,
                    "fallback_used": fallback_used,
                    "turns": copy.deepcopy(turns),
                }
            )
        results.append(
            {
                "case_id": case.get("id"),
                "category": case.get("category"),
                "fresh_task": True,
                "executor_runs": executor_runs,
            }
        )
    return results


def _failure(failures: list[str], case_id: str, message: str) -> None:
    failures.append(f"{case_id}: {message}")


def _verify_turn(
    case_id: str,
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    prompt: str,
    failures: list[str],
) -> None:
    if actual.get("prompt_sha256") != _prompt_hash(prompt):
        _failure(failures, case_id, "prompt_sha256 does not match the retained prompt")
    if "prompt" in actual and actual.get("prompt") != prompt:
        _failure(failures, case_id, "retained prompt differs from the corpus")
    if actual.get("activated") is not expected.get("activated"):
        _failure(
            failures,
            case_id,
            f"activation was {actual.get('activated')!r}; expected {expected.get('activated')!r}",
        )
    if actual.get("skill") != (expected.get("skill") if expected.get("activated") else None):
        _failure(failures, case_id, "selected skill differs from the expected skill")
    if expected.get("activated") and actual.get("plugin") != PLUGIN_NAME:
        _failure(failures, case_id, "active result does not identify the expected plugin")
    required_references = expected.get("required_references", [])
    references = actual.get("references", [])
    if not expected.get("activated"):
        if actual.get("plugin") or actual.get("skill"):
            _failure(failures, case_id, "negative/boundary result activated the plugin")
        if actual.get("tool_calls"):
            _failure(failures, case_id, "negative/boundary result contains tool calls")
    for reference in references if isinstance(references, list) else []:
        if not isinstance(reference, str):
            _failure(failures, case_id, "retained reference paths must be strings")
            continue
        reference_path = PurePosixPath(reference.replace("\\", "/"))
        if reference_path.is_absolute() or ".." in reference_path.parts:
            _failure(failures, case_id, "retained reference path escapes the installed plugin")
    if not isinstance(references, list):
        _failure(failures, case_id, "references must be a list")
        references = []
    for reference in required_references:
        if reference not in references:
            _failure(failures, case_id, f"required reference was not retained: {reference}")
    if required_references and actual.get("references_resolved") is not True:
        _failure(failures, case_id, "bundled references were not marked resolved")
    if expected.get("requires_prior_identifier") and actual.get("identifier_reused") is not True:
        _failure(failures, case_id, "follow-up did not reuse a prior result identifier")
    expected_confirmation = bool(expected.get("requires_confirmation"))
    confirmation = actual.get("confirmation")
    if not isinstance(confirmation, Mapping):
        confirmation = {}
    if expected_confirmation and confirmation.get("requested") is not True:
        _failure(failures, case_id, "write request did not ask for confirmation")
    if not expected_confirmation and confirmation.get("requested") is True:
        _failure(failures, case_id, "read-only request unexpectedly asked for confirmation")
    auth_expected = expected.get("authorization", "not_applicable")
    authorization = actual.get("authorization")
    if not isinstance(authorization, Mapping):
        authorization = {}
    mutated = authorization.get("mutated") is True
    if auth_expected == "deny_without_confirmation":
        if authorization.get("decision") != "denied":
            _failure(failures, case_id, "write request without confirmation was not denied")
        if mutated:
            _failure(failures, case_id, "write request mutated state without confirmation")
        if confirmation.get("provided") is True:
            _failure(failures, case_id, "denied write unexpectedly recorded confirmation")
    elif auth_expected == "allow_exact_digest":
        if authorization.get("decision") != "allowed":
            _failure(failures, case_id, "confirmed write was not authorized")
        if confirmation.get("provided") is not True:
            _failure(failures, case_id, "confirmed write lacks confirmation evidence")
        plan_digest = confirmation.get("plan_digest")
        confirmed_digest = confirmation.get("confirmed_digest")
        if (
            not isinstance(plan_digest, str)
            or not HEX_DIGEST.fullmatch(plan_digest)
            or confirmed_digest != plan_digest
        ):
            _failure(failures, case_id, "confirmed write does not bind the exact plan digest")
    elif mutated:
        _failure(failures, case_id, "unexpected mutation on a non-writing request")


def verify_results(
    suite: Mapping[str, Any],
    results: Sequence[Mapping[str, Any]],
    *,
    installation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify retained conversation results against the deterministic corpus."""

    cases = [value for value in suite.get("cases", []) if isinstance(value, Mapping)]
    expected_by_id = {str(value.get("id")): value for value in cases}
    failures: list[str] = []
    actual_by_id: dict[str, Mapping[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for result in results:
        if not isinstance(result, Mapping):
            failures.append("result records must be JSON objects")
            continue
        if _contains_secret_like_text(result):
            case_id = result.get("case_id", "<unknown>")
            failures.append(f"{case_id}: result contains unredacted credential-like text")
        if result.get("fresh_task") is not True:
            case_id = result.get("case_id", "<unknown>")
            failures.append(f"{case_id}: result was not recorded from a fresh task")
        case_id = result.get("case_id")
        if not isinstance(case_id, str):
            failures.append("result record lacks a case_id")
            continue
        if case_id in actual_by_id:
            duplicate_ids.add(case_id)
        actual_by_id[case_id] = result
    for case_id in sorted(duplicate_ids):
        failures.append(f"{case_id}: duplicate result record")
    for case_id in sorted(set(expected_by_id) - set(actual_by_id)):
        failures.append(f"{case_id}: missing result record")
    for case_id in sorted(set(actual_by_id) - set(expected_by_id)):
        failures.append(f"{case_id}: unexpected result record")
    case_reports: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get("id"))
        case_failures: list[str] = []
        result = actual_by_id.get(case_id)
        if result is None:
            case_failures.append("missing result record")
        else:
            if result.get("fresh_task") is not True:
                case_failures.append("result was not recorded from a fresh task")
            if result.get("category") not in (None, case.get("category")):
                case_failures.append("result category differs from the corpus")
            expected_turns = case.get("expected_turns", [])
            prompts = case.get("turns", [])
            executor_runs = result.get("executor_runs")
            if not isinstance(executor_runs, list):
                case_failures.append("result lacks required MCP available/unavailable runs")
            else:
                expected_modes = set(EXECUTOR_MODES)
                actual_modes = {
                    run.get("mode") for run in executor_runs if isinstance(run, Mapping)
                }
                if actual_modes != expected_modes:
                    case_failures.append(
                        "executor runs must include exactly mcp_available and mcp_unavailable"
                    )
                for run in executor_runs:
                    if not isinstance(run, Mapping):
                        case_failures.append("executor run must be an object")
                        continue
                    mode = run.get("mode")
                    if mode not in expected_modes:
                        continue
                    expected_mcp = "available" if mode == "mcp_available" else "unavailable"
                    if run.get("github_mcp") != expected_mcp:
                        case_failures.append(f"{mode}: GitHub MCP availability is mislabeled")
                    remote_skill = any(
                        expected.get("skill")
                        in {"backlog-init", "backlog-sprint-plan", "backlog-sync-github"}
                        for expected in expected_turns
                        if isinstance(expected, Mapping)
                    )
                    active = any(
                        expected.get("activated") is True
                        for expected in expected_turns
                        if isinstance(expected, Mapping)
                    )
                    if not active:
                        expected_transport = "none"
                        expected_fallback = False
                    elif not remote_skill:
                        expected_transport = "local-engine"
                        expected_fallback = False
                    elif mode == "mcp_available":
                        expected_transport = "github-mcp"
                        expected_fallback = False
                    else:
                        expected_transport = "cli-or-api-fallback"
                        expected_fallback = True
                    if run.get("transport") != expected_transport:
                        case_failures.append(
                            f"{mode}: transport {run.get('transport')!r} does not prove {expected_transport!r}"
                        )
                    if run.get("fallback_used") is not expected_fallback:
                        case_failures.append(
                            f"{mode}: fallback_used does not match the executor contract"
                        )
                    turns = run.get("turns")
                    if not isinstance(turns, list) or len(turns) != len(expected_turns):
                        case_failures.append(f"{mode}: result turn count differs from the corpus")
                        continue
                    for expected, actual, prompt_data in zip(expected_turns, turns, prompts):
                        if not isinstance(actual, Mapping):
                            case_failures.append(f"{mode}: turn result must be an object")
                            continue
                        _verify_turn(
                            case_id,
                            expected,
                            actual,
                            str(prompt_data.get("prompt")),
                            case_failures,
                        )
        failures.extend(f"{case_id}: {value}" for value in case_failures)
        case_reports.append(
            {"case_id": case_id, "category": case.get("category"), "passed": not case_failures, "failures": case_failures}
        )
    if installation is not None and installation.get("passed") is not True:
        failures.extend(
            f"static pickup: {value}" for value in installation.get("failures", [])
        )
    return {
        "schema_version": 1,
        "suite": suite.get("suite"),
        "passed": bool(cases) and not failures,
        "case_count": len(cases),
        "result_count": len(results),
        "categories": list(PROMPT_CATEGORIES),
        "cases": case_reports,
        "failures": failures,
    }


def load_results(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvaluationError(f"Cannot read result evidence {path}: {exc}") from exc
    if path.suffix.lower() == ".json":
        value = json.loads(text)
        if isinstance(value, dict) and isinstance(value.get("results"), list):
            value = value["results"]
        if not isinstance(value, list):
            raise EvaluationError("JSON result evidence must contain a list")
        return [dict(row) for row in value if isinstance(row, Mapping)]
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvaluationError(f"Result evidence line {index} is not JSON: {exc}") from exc
        if not isinstance(value, Mapping):
            raise EvaluationError(f"Result evidence line {index} must be an object")
        rows.append(dict(value))
    return rows


def write_results(path: Path, results: Sequence[Mapping[str, Any]]) -> None:
    """Write one redaction-ready JSON object per line for durable evidence."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(_canonical(dict(value)) + "\n" for value in results),
        encoding="utf-8",
    )
    temporary.replace(path)


def verify_suite(
    suite_path: Path,
    *,
    results_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Verify static install evidence plus retained conversation results."""

    suite_file = Path(suite_path).resolve()
    try:
        suite = _read_json(suite_file)
    except EvaluationError as exc:
        report = {"schema_version": 1, "passed": False, "status": "invalid", "failures": [str(exc)]}
        if report_path:
            _write_json(Path(report_path), report)
        return report
    root = suite_file.parent
    artifacts = suite.get("artifacts", {})
    staged = root / str(artifacts.get("staged_plugin", "workspace/plugins/agentic-backlog-kit"))
    workspace = root / str(artifacts.get("workspace", "workspace"))
    marketplace = root / str(
        artifacts.get("marketplace", "workspace/.agents/plugins/marketplace.json")
    )
    installation = inspect_installation(staged)
    market = _marketplace_check(marketplace, workspace_root=workspace)
    failures: list[str] = []
    if installation.get("manifest", {}).get("sha256") != suite.get("plugin", {}).get("manifest_sha256"):
        failures.append("staged plugin manifest digest differs from the prepared suite")
    if not installation.get("passed"):
        failures.extend(f"static pickup: {value}" for value in installation.get("failures", []))
    if not market.get("passed"):
        failures.extend(f"marketplace: {value}" for value in market.get("failures", []))
    corpus_path = root / str(suite.get("corpus", {}).get("path", "fixtures/evaluation-corpus.json"))
    if not corpus_path.is_file() or _sha256_file(corpus_path) != suite.get("corpus", {}).get("sha256"):
        failures.append("evaluation corpus is missing or changed after preparation")
    selected_results = Path(results_path) if results_path else root / str(
        artifacts.get("results", "results.ndjson")
    )
    if not selected_results.is_file():
        report = {
            "schema_version": 1,
            "suite": suite.get("suite"),
            "passed": False,
            "status": "pending",
            "fresh_task_execution_required": True,
            "case_count": len(suite.get("cases", [])),
            "result_count": 0,
            "static_pickup": installation,
            "marketplace": market,
            "failures": failures + [f"missing conversation results: {selected_results.name}"],
        }
    else:
        try:
            results = load_results(selected_results)
        except EvaluationError as exc:
            results = []
            failures.append(str(exc))
        report = verify_results(suite, results, installation=installation)
        report["status"] = "completed" if report["passed"] and not failures else "failed"
        report["static_pickup"] = installation
        report["marketplace"] = market
        report["failures"] = failures + list(report.get("failures", []))
        report["passed"] = bool(report["passed"] and not failures)
    if report_path:
        _write_json(Path(report_path), report)
    return report


from .trace import (
    TRACE_CASES,
    TRACE_DEFAULT_MAX_OUTPUT_BYTES,
    TRACE_DEFAULT_MODEL,
    TRACE_DEFAULT_REASONING_EFFORT,
    TRACE_DEFAULT_TIMEOUT_SECONDS,
    TRACE_SCHEMA_VERSION,
    parse_trace_jsonl,
    probe_codex_mcp,
    probe_plugin_catalog,
    run_trace_case,
    run_traces,
    seed_trace_workspace,
    verify_trace_records,
    write_trace_records,
)

__all__ = [
    "CORPUS_PATH",
    "EXECUTOR_MODES",
    "EXPECTED_SKILLS",
    "EvaluationError",
    "PROMPT_CATEGORIES",
    "inspect_installation",
    "load_corpus",
    "load_results",
    "prepare_suite",
    "probe_codex_cli",
    "run_diagnostics",
    "synthetic_results",
    "verify_results",
    "verify_suite",
    "write_results",
    "TRACE_CASES",
    "TRACE_DEFAULT_MAX_OUTPUT_BYTES",
    "TRACE_DEFAULT_MODEL",
    "TRACE_DEFAULT_REASONING_EFFORT",
    "TRACE_DEFAULT_TIMEOUT_SECONDS",
    "TRACE_SCHEMA_VERSION",
    "parse_trace_jsonl",
    "probe_codex_mcp",
    "probe_plugin_catalog",
    "run_trace_case",
    "run_traces",
    "seed_trace_workspace",
    "verify_trace_records",
    "write_trace_records",
]
