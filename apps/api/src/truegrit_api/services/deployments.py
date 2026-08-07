"""Ordered testing -> staging -> main release promotion."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import Any

from truegrit_api.errors import ConflictError, ValidationAppError
from truegrit_api.platform.github import GitHubApiError, GitHubClient

AGENT_APPROVAL_CONTEXT = "truegrit/agent-approval"
MANUAL_VERIFICATION_CONTEXT = "truegrit/manual-staging-verification"
BRANCHES = ("testing", "staging", "main")
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SUCCESSFUL_CONCLUSIONS = {"success", "neutral", "skipped"}
_COMMIT_LIMIT = 20


class DeploymentService:
    def __init__(
        self,
        github: GitHubClient,
        *,
        testing_url: str,
        staging_url: str,
        main_url: str,
    ) -> None:
        self.github = github
        self._urls = {"testing": testing_url, "staging": staging_url, "main": main_url}

    async def dashboard(self) -> dict[str, Any]:
        branches = await asyncio.gather(*(self._branch(branch) for branch in BRANCHES))
        return {
            "repository": self.github.repository,
            "canWrite": self.github.can_write,
            "generatedAt": datetime.now(UTC).isoformat(),
            "branches": branches,
        }

    async def verify_staging(self, sha: str, actor_name: str, notes: str) -> dict[str, Any]:
        self._validate_sha(sha)
        clean_notes = " ".join(notes.split())
        if len(clean_notes) < 3 or len(clean_notes) > 100:
            raise ValidationAppError("Verification notes must be between 3 and 100 characters.")
        branch = await self._branch("staging")
        self._assert_current_head(branch, sha)
        if branch["ciState"] != "success":
            raise ConflictError("Staging checks must pass before manual verification.")
        description = f"Verified by {actor_name}: {clean_notes}"
        await self._github_call(
            self.github.create_status(sha, MANUAL_VERIFICATION_CONTEXT, description)
        )
        return {"sha": sha, "verified": True, "description": description[:140]}

    async def promote(self, source: str, target: str, sha: str, actor_name: str) -> dict[str, Any]:
        self._validate_sha(sha)
        required_context = self._promotion_context(source, target)
        branch = await self._branch(source)
        self._assert_current_head(branch, sha)
        if branch["ciState"] != "success":
            raise ConflictError(f"All {source} checks must pass before promotion.")
        if branch["gate"]["context"] != required_context or branch["gate"]["state"] != "success":
            raise ConflictError(branch["blockedReason"] or "Required approval is missing.")
        message = f"Promote {sha[:8]} from {source} to {target} (approved by {actor_name})"
        new_sha, already_current = await self._github_call(self.github.merge(target, sha, message))
        return {
            "source": source,
            "target": target,
            "promotedSha": sha,
            "targetSha": new_sha,
            "alreadyCurrent": already_current,
        }

    async def _branch(self, branch: str) -> dict[str, Any]:
        commits = await self._github_call(self.github.commits(branch, _COMMIT_LIMIT))
        if not commits:
            raise ConflictError(f"GitHub returned no commits for {branch}.")
        head_sha = str(commits[0].get("sha", ""))
        statuses, check_runs = await asyncio.gather(
            self._github_call(self.github.statuses(head_sha)),
            self._github_call(self.github.check_runs(head_sha)),
        )
        gate_context = self._gate_context(branch)
        gate = self._latest_status(statuses, gate_context)
        ci_state, checks = self._check_state(check_runs)
        blocked_reason = self._blocked_reason(branch, ci_state, gate)
        return {
            "name": branch,
            "environmentUrl": self._urls[branch] or None,
            "headSha": head_sha,
            "ciState": ci_state,
            "checks": checks,
            "gate": gate,
            "canPromote": branch != "main" and blocked_reason is None and self.github.can_write,
            "blockedReason": blocked_reason
            or ("Configure GITHUB_TOKEN to enable actions." if not self.github.can_write else None),
            "commits": [self._commit_row(commit) for commit in commits],
        }

    @staticmethod
    def _commit_row(commit: dict[str, Any]) -> dict[str, Any]:
        details = commit.get("commit") if isinstance(commit.get("commit"), dict) else {}
        author = details.get("author") if isinstance(details.get("author"), dict) else {}
        account = commit.get("author") if isinstance(commit.get("author"), dict) else {}
        message = str(details.get("message", "Untitled commit")).splitlines()[0]
        return {
            "sha": str(commit.get("sha", "")),
            "message": message,
            "author": str(account.get("login") or author.get("name") or "Unknown"),
            "authoredAt": str(author.get("date") or ""),
            "url": str(commit.get("html_url") or ""),
        }

    @staticmethod
    def _latest_status(statuses: list[dict[str, Any]], context: str | None) -> dict[str, Any]:
        if context is None:
            return {"context": None, "state": "not-required", "description": None, "actor": None}
        for status in statuses:
            if str(status.get("context", "")).casefold() != context.casefold():
                continue
            creator = status.get("creator") if isinstance(status.get("creator"), dict) else {}
            return {
                "context": context,
                "state": str(status.get("state", "pending")),
                "description": status.get("description"),
                "actor": creator.get("login"),
                "createdAt": status.get("created_at"),
            }
        return {"context": context, "state": "pending", "description": None, "actor": None}

    @staticmethod
    def _check_state(check_runs: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        latest: dict[str, dict[str, Any]] = {}
        for run in check_runs:
            name = str(run.get("name", "Unnamed check"))
            latest.setdefault(name, run)
        checks = [
            {
                "name": name,
                "status": str(run.get("status", "queued")),
                "conclusion": run.get("conclusion"),
                "url": run.get("html_url"),
            }
            for name, run in latest.items()
        ]
        if not checks or any(check["status"] != "completed" for check in checks):
            return "pending", checks
        if any(check["conclusion"] not in _SUCCESSFUL_CONCLUSIONS for check in checks):
            return "failure", checks
        return "success", checks

    @staticmethod
    def _gate_context(branch: str) -> str | None:
        if branch == "testing":
            return AGENT_APPROVAL_CONTEXT
        if branch == "staging":
            return MANUAL_VERIFICATION_CONTEXT
        return None

    @staticmethod
    def _promotion_context(source: str, target: str) -> str:
        pairs = {
            ("testing", "staging"): AGENT_APPROVAL_CONTEXT,
            ("staging", "main"): MANUAL_VERIFICATION_CONTEXT,
        }
        context = pairs.get((source, target))
        if context is None:
            raise ValidationAppError("Promotion must be testing to staging or staging to main.")
        return context

    @staticmethod
    def _blocked_reason(branch: str, ci_state: str, gate: dict[str, Any]) -> str | None:
        if branch == "main":
            return None
        if ci_state == "pending":
            return "Checks are still running."
        if ci_state == "failure":
            return "One or more checks failed."
        if gate["state"] != "success":
            return (
                "Agent approval is required on testing."
                if branch == "testing"
                else "Manual staging verification is required."
            )
        return None

    @staticmethod
    def _assert_current_head(branch: dict[str, Any], sha: str) -> None:
        if branch["headSha"] != sha:
            raise ConflictError("The branch advanced. Refresh and review the new head commit.")

    @staticmethod
    def _validate_sha(sha: str) -> None:
        if not _SHA_PATTERN.fullmatch(sha):
            raise ValidationAppError("A full 40-character commit SHA is required.")

    @staticmethod
    async def _github_call(awaitable: Any) -> Any:
        try:
            return await awaitable
        except GitHubApiError as exc:
            if exc.status in {409, 422}:
                raise ConflictError(str(exc)) from exc
            if exc.status in {401, 403}:
                raise ConflictError("GitHub credentials are missing or lack permission.") from exc
            raise ConflictError("GitHub is temporarily unavailable.") from exc
