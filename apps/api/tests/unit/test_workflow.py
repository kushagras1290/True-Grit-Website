import pytest

from truegrit_api.domain.workflow import allowed_transitions, assert_transition
from truegrit_api.errors import ConflictError, PermissionDeniedError

EDITOR = frozenset({"categories.edit"})
APPROVER = frozenset({"categories.approve"})
PUBLISHER = frozenset({"categories.publish"})
ALL = EDITOR | APPROVER | PUBLISHER


def test_happy_path_transitions():
    assert_transition("categories", "draft", "in_review", EDITOR)
    assert_transition("categories", "in_review", "approved", APPROVER)
    assert_transition("categories", "approved", "published", PUBLISHER)
    assert_transition("categories", "approved", "scheduled", PUBLISHER)
    assert_transition("categories", "scheduled", "published", PUBLISHER)


def test_changes_requested_loops_back_to_draft():
    assert_transition("categories", "in_review", "changes_requested", APPROVER)
    assert_transition("categories", "changes_requested", "draft", EDITOR)


def test_invalid_transitions_rejected():
    with pytest.raises(ConflictError):
        assert_transition("categories", "draft", "published", ALL)
    with pytest.raises(ConflictError):
        assert_transition("categories", "published", "draft", ALL)
    with pytest.raises(ConflictError):
        assert_transition("categories", "draft", "nonsense", ALL)
    with pytest.raises(ConflictError):
        allowed_transitions("bogus")


def test_permission_is_enforced_per_transition():
    with pytest.raises(PermissionDeniedError):
        assert_transition("categories", "in_review", "approved", EDITOR)
    with pytest.raises(PermissionDeniedError):
        assert_transition("categories", "approved", "published", APPROVER)


def test_published_is_terminal_for_versions():
    assert allowed_transitions("published") == frozenset()
