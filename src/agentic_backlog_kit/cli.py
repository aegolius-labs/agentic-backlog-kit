from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .bootstrap import (
    BootstrapExecutor,
    apply_bootstrap_plan,
    bootstrap_plan_from_dict,
    build_bootstrap_plan,
)
from .github import (
    GitHubCliTransport,
    GitHubHttpTransport,
    GitHubPlanExecutor,
    GitHubScaffoldExecutor,
    GitHubService,
)
from .manifest import default_manifest, load_manifest
from .iterations import (
    apply_iteration_plan,
    build_iteration_plan,
    iteration_plan_from_dict,
    verify_iteration_apply,
)
from .mutations import add_item, file_sha256, save_manifest, update_item
from .priority import prioritize, select_next
from .scaffold import (
    apply_scaffold_plan,
    build_scaffold_plan,
    scaffold_plan_from_dict,
)
from .snapshot import (
    GitHubProjectDiscoveryReader,
    GitHubScaffoldSnapshotReader,
    GitHubSnapshotReader,
)
from .sprint import plan_sprint, sprint_plan_payload
from .sync import apply_plan, build_sync_plan, sync_plan_from_dict


DEFAULT_MANIFEST = ".agentic-backlog/manifest.json"


def _write_json(path: Path, data: dict[str, Any], *, force: bool = True) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite: {path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _transport(backend: str):
    gh_path = shutil.which("gh")
    if backend == "gh" or (backend == "auto" and gh_path):
        if not gh_path:
            raise RuntimeError("GitHub CLI backend requested but 'gh' is not installed")
        return GitHubCliTransport(gh_path)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "Direct GitHub API access requires GH_TOKEN or GITHUB_TOKEN; "
            "alternatively install and authenticate GitHub CLI"
        )
    return GitHubHttpTransport(token)


def _read_snapshot(path: str | None, manifest: dict[str, Any], backend: str) -> dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    github = manifest["github"]
    return GitHubSnapshotReader(
        _transport(backend),
        owner=github["owner"],
        repository=github["repository"],
        project_number=github["project_number"],
    ).read()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="abk",
        description="Deterministic GitHub backlog planning and reconciliation",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Create a compact local manifest")
    init.add_argument("--manifest", default=DEFAULT_MANIFEST)
    init.add_argument("--owner", required=True)
    init.add_argument("--repository", required=True)
    init.add_argument("--project-number", type=int, required=True)
    init.add_argument("--force", action="store_true")

    init_plan = commands.add_parser(
        "init-plan", help="Discover or preview creation of an organization Project"
    )
    init_plan.add_argument("--owner", required=True)
    init_plan.add_argument("--repository", required=True)
    init_plan.add_argument("--project-title")
    init_plan.add_argument("--project-number", type=int)
    init_plan.add_argument("--snapshot")
    init_plan.add_argument("--output")
    init_plan.add_argument("--backend", choices=("auto", "gh", "api"), default="auto")

    init_apply = commands.add_parser(
        "init-apply", help="Apply one reviewed bootstrap plan and create the manifest"
    )
    init_apply.add_argument("--manifest", default=DEFAULT_MANIFEST)
    init_apply.add_argument("--plan", required=True)
    init_apply.add_argument("--confirm", required=True)
    init_apply.add_argument("--scaffold-plan")
    init_apply.add_argument(
        "--receipt", default=".agentic-backlog/receipts/init-apply.json"
    )
    init_apply.add_argument("--force", action="store_true")
    init_apply.add_argument("--backend", choices=("auto", "gh", "api"), default="auto")

    validate = commands.add_parser("validate", help="Validate without mutation")
    validate.add_argument("--manifest", default=DEFAULT_MANIFEST)

    priority = commands.add_parser("prioritize", help="Compute concise priority order")
    priority.add_argument("--manifest", default=DEFAULT_MANIFEST)
    priority.add_argument("--limit", type=int, default=20)

    next_item = commands.add_parser("next", help="Return the next executable item")
    next_item.add_argument("--manifest", default=DEFAULT_MANIFEST)

    sprint = commands.add_parser("sprint-plan", help="Plan a dependency-safe sprint")
    sprint.add_argument("--manifest", default=DEFAULT_MANIFEST)
    sprint.add_argument("--capacity", type=int)
    sprint.add_argument("--sprint")
    sprint.add_argument("--snapshot", help="Fresh Project scaffold snapshot for target validation")
    sprint.add_argument("--as-of", help="ISO date used to resolve @current and @next")
    sprint.add_argument("--backend", choices=("auto", "gh", "api"), default="auto")
    sprint.add_argument(
        "--skipped-limit",
        type=int,
        help="Project the skipped-item reasons to this many entries",
    )

    show = commands.add_parser("show", help="Return one compact backlog item")
    show.add_argument("item_id")
    show.add_argument("--manifest", default=DEFAULT_MANIFEST)

    summary = commands.add_parser("summary", help="Return compact backlog counts")
    summary.add_argument("--manifest", default=DEFAULT_MANIFEST)

    item_add = commands.add_parser("item-add", help="Validate and add one item")
    item_add.add_argument("--manifest", default=DEFAULT_MANIFEST)
    item_add.add_argument("--input", required=True)

    item_update = commands.add_parser("item-update", help="Validate and patch one item")
    item_update.add_argument("item_id")
    item_update.add_argument("--manifest", default=DEFAULT_MANIFEST)
    item_update.add_argument("--input", required=True)

    snapshot = commands.add_parser("snapshot", help="Read managed state from GitHub")
    snapshot.add_argument("--manifest", default=DEFAULT_MANIFEST)
    snapshot.add_argument("--output")
    snapshot.add_argument("--backend", choices=("auto", "gh", "api"), default="auto")

    sync_plan = commands.add_parser("sync-plan", help="Preview GitHub changes")
    sync_plan.add_argument("--manifest", default=DEFAULT_MANIFEST)
    sync_plan.add_argument("--snapshot")
    sync_plan.add_argument("--output")
    sync_plan.add_argument("--backend", choices=("auto", "gh", "api"), default="auto")
    sync_plan.add_argument("--preserve-body", action="store_true")

    sync_apply = commands.add_parser(
        "sync-apply", help="Apply one exact reviewed plan"
    )
    sync_apply.add_argument("--manifest", default=DEFAULT_MANIFEST)
    sync_apply.add_argument("--plan", required=True)
    sync_apply.add_argument("--confirm", required=True)
    sync_apply.add_argument(
        "--receipt", default=".agentic-backlog/receipts/sync-apply.json"
    )
    sync_apply.add_argument("--backend", choices=("auto", "gh", "api"), default="auto")

    scaffold_snapshot = commands.add_parser(
        "scaffold-snapshot", help="Read GitHub Project fields, views, and labels"
    )
    scaffold_snapshot.add_argument("--manifest", default=DEFAULT_MANIFEST)
    scaffold_snapshot.add_argument("--output")
    scaffold_snapshot.add_argument(
        "--backend", choices=("auto", "gh", "api"), default="auto"
    )

    scaffold_plan = commands.add_parser(
        "scaffold-plan", help="Preview fields, labels, and Agile views"
    )
    scaffold_plan.add_argument("--manifest", default=DEFAULT_MANIFEST)
    scaffold_plan.add_argument("--snapshot")
    scaffold_plan.add_argument("--output")
    scaffold_plan.add_argument(
        "--backend", choices=("auto", "gh", "api"), default="auto"
    )

    scaffold_apply = commands.add_parser(
        "scaffold-apply", help="Apply one exact reviewed scaffold plan"
    )
    scaffold_apply.add_argument("--manifest", default=DEFAULT_MANIFEST)
    scaffold_apply.add_argument("--plan", required=True)
    scaffold_apply.add_argument("--confirm", required=True)
    scaffold_apply.add_argument(
        "--receipt", default=".agentic-backlog/receipts/scaffold-apply.json"
    )
    scaffold_apply.add_argument(
        "--backend", choices=("auto", "gh", "api"), default="auto"
    )

    iteration_plan = commands.add_parser(
        "iteration-plan", help="Resolve or preview a safe Project iteration lifecycle update"
    )
    iteration_plan.add_argument("--manifest", default=DEFAULT_MANIFEST)
    iteration_plan.add_argument("--target", required=True)
    iteration_plan.add_argument("--as-of")
    iteration_plan.add_argument("--snapshot")
    iteration_plan.add_argument("--output")
    iteration_plan.add_argument(
        "--backend", choices=("auto", "gh", "api"), default="auto"
    )

    iteration_apply = commands.add_parser(
        "iteration-apply", help="Apply one exact reviewed iteration lifecycle plan"
    )
    iteration_apply.add_argument("--manifest", default=DEFAULT_MANIFEST)
    iteration_apply.add_argument("--plan", required=True)
    iteration_apply.add_argument("--confirm", required=True)
    iteration_apply.add_argument(
        "--receipt", default=".agentic-backlog/receipts/iteration-apply.json"
    )
    iteration_apply.add_argument(
        "--backend", choices=("auto", "gh", "api"), default="auto"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "init":
        path = Path(args.manifest)
        data = default_manifest(args.owner, args.repository, args.project_number)
        _write_json(path, data, force=args.force)
        _print_json({"manifest": str(path), "schema_version": data["schema_version"]})
        return 0

    if args.command == "init-plan":
        if args.snapshot:
            discovery = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        else:
            discovery = GitHubProjectDiscoveryReader(
                _transport(args.backend),
                owner=args.owner,
                repository=args.repository,
                project_title=args.project_title,
                project_number=args.project_number,
            ).read()
        plan = build_bootstrap_plan(
            args.owner,
            args.repository,
            discovery,
            project_title=args.project_title,
            project_number=args.project_number,
        )
        payload = plan.as_dict()
        if args.output:
            _write_json(Path(args.output), payload)
            _print_json(
                {
                    "plan": args.output,
                    "digest": plan.digest,
                    "actions": len(plan.actions),
                    "project": plan.project,
                }
            )
        else:
            _print_json(payload)
        return 0

    if args.command == "init-apply":
        manifest_path = Path(args.manifest)
        if manifest_path.exists() and not args.force:
            raise FileExistsError(
                f"Refusing to overwrite: {manifest_path} already exists"
            )
        raw_plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        plan = bootstrap_plan_from_dict(raw_plan)
        transport = _transport(args.backend)
        discovery = GitHubProjectDiscoveryReader(
            transport,
            owner=plan.owner,
            repository=plan.repository,
            project_title=plan.project_title,
            project_number=plan.requested_project_number,
        ).read()
        service = GitHubService(
            transport,
            owner=plan.owner,
            repository=plan.repository,
            project_number=plan.project["number"] if plan.project else 1,
        )
        result = apply_bootstrap_plan(
            plan,
            executor=BootstrapExecutor(service),
            confirmation=args.confirm,
            discovery_snapshot=discovery,
            journal=lambda value: _write_json(Path(args.receipt), asdict(value)),
        )
        manifest = default_manifest(
            plan.owner, plan.repository, result.project["number"]
        )
        _write_json(manifest_path, manifest, force=args.force)

        # Creation returns identity, but GitHub may also create default fields/views.
        # Refresh those before proposing the separately reviewed scaffold plan.
        snapshot = GitHubScaffoldSnapshotReader(
            transport,
            owner=plan.owner,
            repository=plan.repository,
            project_number=result.project["number"],
        ).read()
        next_plan = build_scaffold_plan(manifest, snapshot)
        next_payload = next_plan.as_dict()
        if args.scaffold_plan:
            _write_json(Path(args.scaffold_plan), next_payload)
        _print_json(
            {
                "manifest": str(manifest_path),
                "project": result.project,
                "plan_digest": plan.digest,
                "applied_actions": result.applied_actions,
                "scaffold_plan": args.scaffold_plan,
                "scaffold_digest": next_plan.digest,
                "scaffold_actions": len(next_plan.actions),
            }
        )
        return 0

    manifest = load_manifest(args.manifest)
    if args.command == "validate":
        _print_json(
            {
                "valid": True,
                "schema_version": manifest["schema_version"],
                "items": len(manifest["items"]),
            }
        )
        return 0
    if args.command == "prioritize":
        items = [asdict(item) for item in prioritize(manifest)[: max(args.limit, 0)]]
        _print_json({"count": len(items), "items": items})
        return 0
    if args.command == "next":
        item = select_next(manifest)
        _print_json({"item": asdict(item) if item else None})
        return 0
    if args.command == "sprint-plan":
        project_snapshot = None
        if args.sprint:
            if args.snapshot:
                project_snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
            else:
                github = manifest["github"]
                project_snapshot = GitHubScaffoldSnapshotReader(
                    _transport(args.backend),
                    owner=github["owner"],
                    repository=github["repository"],
                    project_number=github["project_number"],
                ).read()
        plan = plan_sprint(
            manifest,
            capacity=args.capacity,
            sprint=args.sprint,
            project_snapshot=project_snapshot,
            as_of=args.as_of,
        )
        payload = sprint_plan_payload(plan, skipped_limit=args.skipped_limit)
        _print_json(payload)
        return 0
    if args.command == "show":
        item = next(
            (entry for entry in manifest["items"] if entry["id"] == args.item_id),
            None,
        )
        if item is None:
            raise KeyError(f"Backlog item '{args.item_id}' was not found")
        score = next(entry for entry in prioritize(manifest) if entry.id == args.item_id)
        _print_json({"item": item, "scores": asdict(score)})
        return 0
    if args.command == "summary":
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for item in manifest["items"]:
            by_type[item["type"]] = by_type.get(item["type"], 0) + 1
            by_status[item["status"]] = by_status.get(item["status"], 0) + 1
        _print_json(
            {
                "items": len(manifest["items"]),
                "by_type": dict(sorted(by_type.items())),
                "by_status": dict(sorted(by_status.items())),
            }
        )
        return 0
    if args.command in {"item-add", "item-update"}:
        path = Path(args.manifest)
        expected = file_sha256(path)
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if args.command == "item-add":
            updated, item_id = add_item(manifest, payload)
        else:
            item_id = args.item_id
            updated = update_item(manifest, item_id, payload)
        result_hash = save_manifest(path, updated, expected_sha256=expected)
        _print_json({"item_id": item_id, "manifest_sha256": result_hash})
        return 0
    if args.command == "snapshot":
        snapshot = _read_snapshot(None, manifest, args.backend)
        if args.output:
            _write_json(Path(args.output), snapshot)
            _print_json({"snapshot": args.output, "issues": len(snapshot["issues"])})
        else:
            _print_json(snapshot)
        return 0
    if args.command == "sync-plan":
        snapshot = _read_snapshot(args.snapshot, manifest, args.backend)
        plan = build_sync_plan(
            manifest, snapshot, manage_body=not args.preserve_body
        )
        payload = plan.as_dict()
        if args.output:
            _write_json(Path(args.output), payload)
            _print_json(
                {
                    "plan": args.output,
                    "digest": plan.digest,
                    "actions": len(plan.actions),
                }
            )
        else:
            _print_json(payload)
        return 0
    if args.command == "sync-apply":
        raw_plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        plan = sync_plan_from_dict(raw_plan)
        fresh_manifest = load_manifest(args.manifest)
        github = fresh_manifest["github"]
        transport = _transport(args.backend)
        snapshot = GitHubSnapshotReader(
            transport,
            owner=github["owner"],
            repository=github["repository"],
            project_number=github["project_number"],
        ).read()
        service = GitHubService(
            transport,
            owner=github["owner"],
            repository=github["repository"],
            project_number=github["project_number"],
            issue_type_mode=github["issue_type_mode"],
        )
        receipt = apply_plan(
            plan,
            executor=GitHubPlanExecutor(service, remote_snapshot=snapshot),
            confirmation=args.confirm,
            manifest=fresh_manifest,
            remote_snapshot=snapshot,
            journal=lambda value: _write_json(Path(args.receipt), asdict(value)),
        )
        payload = asdict(receipt)
        _print_json(payload)
        return 0
    if args.command in {"scaffold-snapshot", "scaffold-plan"}:
        github = manifest["github"]
        if args.command == "scaffold-plan" and args.snapshot:
            snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        else:
            snapshot = GitHubScaffoldSnapshotReader(
                _transport(args.backend),
                owner=github["owner"],
                repository=github["repository"],
                project_number=github["project_number"],
            ).read()
        if args.command == "scaffold-snapshot":
            if args.output:
                _write_json(Path(args.output), snapshot)
                _print_json({"snapshot": args.output})
            else:
                _print_json(snapshot)
            return 0
        plan = build_scaffold_plan(manifest, snapshot)
        payload = plan.as_dict()
        if args.output:
            _write_json(Path(args.output), payload)
            _print_json(
                {
                    "plan": args.output,
                    "digest": plan.digest,
                    "actions": len(plan.actions),
                }
            )
        else:
            _print_json(payload)
        return 0
    if args.command == "iteration-plan":
        github = manifest["github"]
        if args.snapshot:
            snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        else:
            snapshot = GitHubScaffoldSnapshotReader(
                _transport(args.backend),
                owner=github["owner"],
                repository=github["repository"],
                project_number=github["project_number"],
            ).read()
        plan = build_iteration_plan(
            manifest, snapshot, target=args.target, as_of=args.as_of
        )
        payload = plan.as_dict()
        if args.output:
            _write_json(Path(args.output), payload)
            _print_json(
                {
                    "plan": args.output,
                    "digest": plan.digest,
                    "target": plan.target,
                    "resolved_title": plan.resolved_title,
                    "ready": plan.ready,
                    "actions": len(plan.actions),
                }
            )
        else:
            _print_json(payload)
        return 0
    if args.command == "iteration-apply":
        raw_plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        plan = iteration_plan_from_dict(raw_plan)
        fresh_manifest = load_manifest(args.manifest)
        github = fresh_manifest["github"]
        transport = _transport(args.backend)
        reader = GitHubScaffoldSnapshotReader(
            transport,
            owner=github["owner"],
            repository=github["repository"],
            project_number=github["project_number"],
        )
        snapshot = reader.read()
        service = GitHubService(
            transport,
            owner=github["owner"],
            repository=github["repository"],
            project_number=github["project_number"],
            issue_type_mode=github["issue_type_mode"],
        )
        result = apply_iteration_plan(
            plan,
            executor=GitHubScaffoldExecutor(service),
            confirmation=args.confirm,
            manifest=fresh_manifest,
            project_snapshot=snapshot,
            journal=lambda value: _write_json(Path(args.receipt), asdict(value)),
        )
        verified = verify_iteration_apply(plan, fresh_manifest, reader.read())
        _print_json(
            {
                **asdict(result),
                "verified": True,
                "resolved_title": verified.resolved_title,
                "resolved_iteration_id": verified.resolved_iteration_id,
                "remaining_actions": len(verified.actions),
            }
        )
        return 0
    if args.command == "scaffold-apply":
        raw_plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        plan = scaffold_plan_from_dict(raw_plan)
        fresh_manifest = load_manifest(args.manifest)
        github = fresh_manifest["github"]
        transport = _transport(args.backend)
        snapshot = GitHubScaffoldSnapshotReader(
            transport,
            owner=github["owner"],
            repository=github["repository"],
            project_number=github["project_number"],
        ).read()
        service = GitHubService(
            transport,
            owner=github["owner"],
            repository=github["repository"],
            project_number=github["project_number"],
            issue_type_mode=github["issue_type_mode"],
        )
        receipt = apply_scaffold_plan(
            plan,
            executor=GitHubScaffoldExecutor(service),
            confirmation=args.confirm,
            manifest=fresh_manifest,
            project_snapshot=snapshot,
            journal=lambda value: _write_json(Path(args.receipt), asdict(value)),
        )
        _print_json(asdict(receipt))
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")
