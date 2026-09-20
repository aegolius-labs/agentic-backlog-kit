"""Prove a transport can finish a plan before it starts one (R13).

Native GitHub Projects access is a transport invariant, not an MCP-only
feature: a capability-complete host integration, an authenticated GitHub CLI,
and direct GraphQL/REST are peer routes over the same deterministic engine.
Peer status is a claim, though, and the kit had no way to check it - a route was
selected and the apply simply began, so an incomplete route failed partway
through with writes already committed.

This is the check that claim needs. Every action kind declares the capabilities
it requires, every transport declares the capabilities it provides, and an
apply refuses before its first write when the selected route cannot finish.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


class CapabilityError(RuntimeError):
    """Raised when a route cannot perform every operation a plan requires."""


# One name per distinct GitHub surface, because that is the granularity at
# which a route is actually incomplete: the generic GitHub MCP evaluated in
# Wave C could write issues while exposing no Projects surface at all.
ISSUE_WRITE = "issue.write"
ISSUE_HIERARCHY = "issue.hierarchy"
ISSUE_DEPENDENCY = "issue.dependency"
PROJECT_ITEM_WRITE = "project.item.write"
PROJECT_FIELD_WRITE = "project.field.write"
PROJECT_ITERATION_WRITE = "project.iteration.write"
PROJECT_VIEW_WRITE = "project.view.write"
PROJECT_LIFECYCLE = "project.lifecycle"
REPOSITORY_LABEL_WRITE = "repository.label.write"

ALL_CAPABILITIES = frozenset(
    {
        ISSUE_WRITE,
        ISSUE_HIERARCHY,
        ISSUE_DEPENDENCY,
        PROJECT_ITEM_WRITE,
        PROJECT_FIELD_WRITE,
        PROJECT_ITERATION_WRITE,
        PROJECT_VIEW_WRITE,
        PROJECT_LIFECYCLE,
        REPOSITORY_LABEL_WRITE,
    }
)

ACTION_CAPABILITIES: dict[str, frozenset[str]] = {
    # sync
    "issue.create": frozenset({ISSUE_WRITE}),
    "issue.update": frozenset({ISSUE_WRITE}),
    "issue.set_parent": frozenset({ISSUE_HIERARCHY}),
    "issue.add_dependency": frozenset({ISSUE_DEPENDENCY}),
    "project.add_item": frozenset({PROJECT_ITEM_WRITE}),
    "project.set_fields": frozenset({PROJECT_ITEM_WRITE}),
    "project.transition": frozenset({PROJECT_ITEM_WRITE}),
    # import
    "issue.adopt": frozenset({ISSUE_WRITE}),
    # scaffold
    "project.field.create": frozenset({PROJECT_FIELD_WRITE}),
    "project.field.update_options": frozenset({PROJECT_FIELD_WRITE}),
    "project.field.update_iterations": frozenset({PROJECT_ITERATION_WRITE}),
    "project.view.create": frozenset({PROJECT_VIEW_WRITE}),
    "project.view.update": frozenset({PROJECT_VIEW_WRITE}),
    "repository.label.create": frozenset({REPOSITORY_LABEL_WRITE}),
    # bootstrap
    "project.create": frozenset({PROJECT_LIFECYCLE}),
    "project.link_repository": frozenset({PROJECT_LIFECYCLE}),
}


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    route: str
    required: frozenset[str]
    provided: frozenset[str]
    missing: frozenset[str]
    unsupported_actions: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.missing and not self.unsupported_actions

    def as_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "complete": self.complete,
            "required": sorted(self.required),
            "provided": sorted(self.provided),
            "missing": sorted(self.missing),
            "unsupported_actions": list(self.unsupported_actions),
        }


def route_name(transport: Any) -> str:
    """Name the route in the words the operator selected it with."""

    return str(getattr(transport, "route", type(transport).__name__))


def provided_capabilities(transport: Any) -> frozenset[str]:
    """Return what a transport claims it can do.

    A transport that declares nothing is assumed complete.  Both supported
    native routes are proven peers, and silently treating an unknown transport
    as incapable would break callers that supply their own.
    """

    declared = getattr(transport, "capabilities", None)
    if declared is None:
        return ALL_CAPABILITIES
    return frozenset(declared)


def required_capabilities(action_kinds: Iterable[str]) -> tuple[frozenset[str], tuple[str, ...]]:
    """Return the capabilities a set of actions needs, and any unknown kinds."""

    required: set[str] = set()
    unknown: list[str] = []
    for kind in sorted(set(action_kinds)):
        needed = ACTION_CAPABILITIES.get(kind)
        if needed is None:
            unknown.append(kind)
            continue
        required |= needed
    return frozenset(required), tuple(unknown)


def inspect_route(transport: Any, action_kinds: Iterable[str]) -> CapabilityReport:
    """Compare what a plan needs against what the selected route provides."""

    required, unknown = required_capabilities(action_kinds)
    provided = provided_capabilities(transport)
    return CapabilityReport(
        route=route_name(transport),
        required=required,
        provided=provided,
        missing=frozenset(required - provided),
        unsupported_actions=unknown,
    )


def require_capabilities(transport: Any, action_kinds: Iterable[str]) -> CapabilityReport:
    """Refuse an apply the selected route cannot finish, before its first write.

    Failing here rather than partway through is the whole point: a partial
    apply leaves GitHub in a state no plan describes, and the fix is a new
    reviewed plan rather than a retry.
    """

    report = inspect_route(transport, action_kinds)
    if report.unsupported_actions:
        raise CapabilityError(
            f"Route '{report.route}' was asked for unknown action kinds: "
            + ", ".join(report.unsupported_actions)
        )
    if report.missing:
        raise CapabilityError(
            f"Route '{report.route}' cannot complete this plan; it is missing "
            + ", ".join(sorted(report.missing))
            + ". Select a capability-complete route rather than mixing "
            "transports within one apply."
        )
    return report


__all__ = [
    "ACTION_CAPABILITIES",
    "ALL_CAPABILITIES",
    "CapabilityError",
    "CapabilityReport",
    "inspect_route",
    "provided_capabilities",
    "require_capabilities",
    "required_capabilities",
    "route_name",
]
