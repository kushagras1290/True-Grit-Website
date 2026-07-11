"""Content publishing workflow (categories, products, pages, articles, recipes).

Draft -> In Review -> (Changes Requested -> Draft) | Approved -> Scheduled/Published.
Published versions are immutable; editing after publish creates a new draft version.
Transitions are permission-gated and validated centrally — no endpoint may set an
arbitrary state.
"""

from __future__ import annotations

from truegrit_api.errors import ConflictError, PermissionDeniedError

WORKFLOW_STATES = frozenset(
    {"draft", "in_review", "changes_requested", "approved", "scheduled", "published"}
)

_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"in_review"}),
    "in_review": frozenset({"changes_requested", "approved"}),
    "changes_requested": frozenset({"draft", "in_review"}),
    "approved": frozenset({"scheduled", "published"}),
    "scheduled": frozenset({"published", "approved"}),
    "published": frozenset(),
}

# Permission suffix required to perform each transition, resolved against the
# entity's permission domain (e.g. "categories" + ".approve").
_TRANSITION_PERMISSION_SUFFIX: dict[str, str] = {
    "in_review": ".edit",
    "changes_requested": ".approve",
    "draft": ".edit",
    "approved": ".approve",
    "scheduled": ".publish",
    "published": ".publish",
}


def allowed_transitions(current: str) -> frozenset[str]:
    if current not in WORKFLOW_STATES:
        raise ConflictError(f"Unknown workflow state '{current}'.")
    return _TRANSITIONS[current]


def required_permission(entity_domain: str, target: str) -> str:
    suffix = _TRANSITION_PERMISSION_SUFFIX.get(target)
    if suffix is None:
        raise ConflictError(f"Unknown workflow target state '{target}'.")
    return f"{entity_domain}{suffix}"


def assert_transition(
    entity_domain: str,
    current: str,
    target: str,
    actor_permissions: frozenset[str] | set[str],
) -> None:
    """Raise unless the actor may move `current` -> `target` for this entity domain."""
    if target not in WORKFLOW_STATES:
        raise ConflictError(f"Unknown workflow state '{target}'.")
    if target not in allowed_transitions(current):
        raise ConflictError(
            f"Cannot move from '{current}' to '{target}'.",
        )
    permission = required_permission(entity_domain, target)
    if permission not in actor_permissions:
        raise PermissionDeniedError()
