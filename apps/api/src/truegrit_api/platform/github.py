"""Small, allow-listed GitHub REST client used by the release cockpit."""

from __future__ import annotations

import json
import base64
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

_API_ROOT = "https://api.github.com"
_TIMEOUT_SECONDS = 8.0
_MAX_RESPONSE_BYTES = 2_000_000


class GitHubApiError(Exception):
    """GitHub rejected a request or returned an unusable response."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class GitHubResponse:
    status: int
    body: Any


class GitHubClient:
    """GitHub API client confined to one repository configured at startup."""

    def __init__(self, repository: str, token: str, api_version: str) -> None:
        owner, separator, repo = repository.partition("/")
        if not separator or not owner or not repo or "/" in repo:
            raise ValueError("GITHUB_REPOSITORY must have the form owner/repository.")
        self.repository = repository
        self._token = token
        self._api_version = api_version

    @property
    def can_write(self) -> bool:
        return bool(self._token)

    def _url(self, path: str) -> str:
        return f"{_API_ROOT}/repos/{self.repository}{path}"

    def _headers(self) -> dict[str, str]:
        headers = {
            "accept": "application/vnd.github+json",
            "x-github-api-version": self._api_version,
            "user-agent": "truegrit-release-cockpit",
        }
        if self._token:
            headers["authorization"] = f"Bearer {self._token}"
        return headers

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        accepted: frozenset[int] = frozenset({200}),
    ) -> GitHubResponse:
        payload = json.dumps(body) if body is not None else None
        try:
            from js import Object  # Cloudflare Workers runtime only
            from js import fetch as js_fetch
            from pyodide.ffi import to_js
        except (ImportError, ModuleNotFoundError):
            return self._request_local(method, path, payload, accepted)

        options = to_js(
            {
                "method": method,
                "headers": self._headers(),
                **({"body": payload} if payload is not None else {}),
            },
            dict_converter=Object.fromEntries,
        )
        try:
            response = await js_fetch(self._url(path), options)
            text = str(await response.text())
        except Exception as exc:
            raise GitHubApiError(503, "GitHub could not be reached.") from exc
        status = int(response.status)
        if status not in accepted:
            raise GitHubApiError(status, self._safe_error(text, status))
        return GitHubResponse(status, self._decode(text, status))

    def _request_local(
        self, method: str, path: str, payload: str | None, accepted: frozenset[int]
    ) -> GitHubResponse:
        request = urllib.request.Request(
            self._url(path),
            data=payload.encode("utf-8") if payload is not None else None,
            headers=self._headers() | ({"content-type": "application/json"} if payload else {}),
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                status = response.status
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raw = exc.read(_MAX_RESPONSE_BYTES)
            raise GitHubApiError(
                exc.code, self._safe_error(raw.decode("utf-8", "replace"), exc.code)
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GitHubApiError(503, "GitHub could not be reached.") from exc
        if status not in accepted:
            raise GitHubApiError(status, f"GitHub returned HTTP {status}.")
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise GitHubApiError(502, "GitHub returned an oversized response.")
        return GitHubResponse(status, self._decode(raw.decode("utf-8"), status))

    @staticmethod
    def _decode(text: str, status: int) -> Any:
        if status == 204 or not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise GitHubApiError(502, "GitHub returned invalid JSON.") from exc

    @staticmethod
    def _safe_error(text: str, status: int) -> str:
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            return f"GitHub returned HTTP {status}."
        message = body.get("message") if isinstance(body, dict) else None
        return str(message)[:240] if message else f"GitHub returned HTTP {status}."

    async def commits(self, branch: str, limit: int) -> list[dict[str, Any]]:
        response = await self.request("GET", f"/commits?sha={branch}&per_page={limit}")
        return response.body if isinstance(response.body, list) else []

    async def statuses(self, sha: str) -> list[dict[str, Any]]:
        response = await self.request("GET", f"/commits/{sha}/statuses?per_page=100")
        return response.body if isinstance(response.body, list) else []

    async def workflow_runs(self, sha: str) -> list[dict[str, Any]]:
        """Return Actions runs for a commit without requiring Checks permission.

        GitHub currently does not offer the ``Checks`` repository permission in
        the fine-grained personal-access-token UI.  Workflow runs expose the CI
        fields the cockpit needs (name, status, conclusion, and URL) through the
        available ``Actions: read`` permission instead.
        """
        response = await self.request("GET", f"/actions/runs?head_sha={sha}&per_page=100")
        body = response.body if isinstance(response.body, dict) else {}
        runs = body.get("workflow_runs", [])
        return runs if isinstance(runs, list) else []

    async def create_status(self, sha: str, context: str, description: str) -> None:
        await self.request(
            "POST",
            f"/statuses/{sha}",
            body={"state": "success", "context": context, "description": description[:140]},
            accepted=frozenset({201}),
        )

    async def get_file(self, path: str, ref: str = "main") -> dict[str, Any] | None:
        quoted = urllib.parse.quote(path, safe="/")
        try:
            response = await self.request(
                "GET",
                f"/contents/{quoted}?ref={urllib.parse.quote(ref, safe='')}",
                accepted=frozenset({200, 404}),
            )
        except GitHubApiError as exc:
            if exc.status == 404:
                return None
            raise
        if response.status == 404:
            return None
        return response.body if isinstance(response.body, dict) else None

    async def put_file(
        self,
        *,
        path: str,
        content: bytes,
        message: str,
        branch: str = "main",
        sha: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content).decode("ascii"),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha
        quoted = urllib.parse.quote(path, safe="/")
        response = await self.request(
            "PUT",
            f"/contents/{quoted}",
            body=body,
            accepted=frozenset({200, 201}),
        )
        return response.body if isinstance(response.body, dict) else {}

    async def merge(self, base: str, head: str, message: str) -> tuple[str | None, bool]:
        response = await self.request(
            "POST",
            "/merges",
            body={"base": base, "head": head, "commit_message": message},
            accepted=frozenset({201, 204}),
        )
        if response.status == 204:
            return None, True
        body = response.body if isinstance(response.body, dict) else {}
        sha = body.get("sha")
        return (str(sha) if sha else None), False
