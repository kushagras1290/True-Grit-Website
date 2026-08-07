from __future__ import annotations

import asyncio

import pytest

from truegrit_api.errors import ConflictError, ValidationAppError
from truegrit_api.services.deployments import (
    AGENT_APPROVAL_CONTEXT,
    MANUAL_VERIFICATION_CONTEXT,
    DeploymentService,
)

TESTING_SHA = "a" * 40
STAGING_SHA = "b" * 40
MAIN_SHA = "c" * 40


class FakeGitHub:
    repository = "owner/repo"
    can_write = True

    def __init__(self) -> None:
        self.heads = {"testing": TESTING_SHA, "staging": STAGING_SHA, "main": MAIN_SHA}
        self.status_by_sha: dict[str, list[dict[str, object]]] = {
            TESTING_SHA: [
                {
                    "context": AGENT_APPROVAL_CONTEXT,
                    "state": "success",
                    "description": "Approved by codex",
                    "creator": {"login": "github-actions"},
                }
            ],
            STAGING_SHA: [],
            MAIN_SHA: [],
        }
        self.created_statuses: list[tuple[str, str, str]] = []
        self.merges: list[tuple[str, str, str]] = []

    async def commits(self, branch: str, _limit: int) -> list[dict[str, object]]:
        sha = self.heads[branch]
        return [
            {
                "sha": sha,
                "html_url": f"https://github.test/commit/{sha}",
                "author": {"login": "author"},
                "commit": {
                    "message": f"Head of {branch}\n\nDetails",
                    "author": {"name": "Author", "date": "2026-08-07T10:00:00Z"},
                },
            }
        ]

    async def statuses(self, sha: str) -> list[dict[str, object]]:
        return self.status_by_sha[sha]

    async def check_runs(self, _sha: str) -> list[dict[str, object]]:
        return [
            {
                "name": "CI",
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://github.test/run/1",
            }
        ]

    async def create_status(self, sha: str, context: str, description: str) -> None:
        self.created_statuses.append((sha, context, description))
        self.status_by_sha[sha] = [
            {"context": context, "state": "success", "description": description, "creator": {}}
        ]

    async def merge(self, base: str, head: str, message: str) -> tuple[str, bool]:
        self.merges.append((base, head, message))
        return "d" * 40, False


def service(github: FakeGitHub) -> DeploymentService:
    return DeploymentService(
        github,  # type: ignore[arg-type]
        testing_url="",
        staging_url="https://staging.example.test",
        main_url="https://example.test",
    )


def test_testing_agent_approval_unlocks_only_staging() -> None:
    github = FakeGitHub()

    result = asyncio.run(service(github).promote("testing", "staging", TESTING_SHA, "Owner"))

    assert result["targetSha"] == "d" * 40
    assert github.merges[0][0:2] == ("staging", TESTING_SHA)
    with pytest.raises(ValidationAppError):
        asyncio.run(service(github).promote("testing", "main", TESTING_SHA, "Owner"))


def test_staging_verification_records_exact_commit_then_unlocks_main() -> None:
    github = FakeGitHub()
    deployment_service = service(github)

    asyncio.run(
        deployment_service.verify_staging(STAGING_SHA, "Owner", "Checkout and login passed")
    )
    result = asyncio.run(deployment_service.promote("staging", "main", STAGING_SHA, "Owner"))

    assert github.created_statuses[0][0:2] == (STAGING_SHA, MANUAL_VERIFICATION_CONTEXT)
    assert result["promotedSha"] == STAGING_SHA
    assert github.merges[0][0:2] == ("main", STAGING_SHA)


def test_branch_advance_invalidates_reviewed_sha() -> None:
    github = FakeGitHub()

    with pytest.raises(ConflictError, match="branch advanced"):
        asyncio.run(service(github).promote("testing", "staging", "d" * 40, "Owner"))


def test_failed_check_locks_promotion() -> None:
    github = FakeGitHub()

    async def failed_checks(_sha: str) -> list[dict[str, object]]:
        return [{"name": "CI", "status": "completed", "conclusion": "failure"}]

    github.check_runs = failed_checks  # type: ignore[method-assign]

    with pytest.raises(ConflictError, match="checks must pass"):
        asyncio.run(service(github).promote("testing", "staging", TESTING_SHA, "Owner"))
