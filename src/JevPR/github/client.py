from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt


@dataclass(slots=True)
class GitHubClient:
    base_url: str = "https://api.github.com"
    token: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_json(self, path: str) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, headers=self._headers(), timeout=30) as client:
            response = await client.get(path)
            response.raise_for_status()
            return response.json()

    async def list_pull_request_files(
        self,
        *,
        owner: str,
        repo: str,
        pull_number: int,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        page = 1

        while True:
            response = await self.get_json(
                f"/repos/{owner}/{repo}/pulls/{pull_number}/files?per_page={per_page}&page={page}"
            )
            if not isinstance(response, list):
                raise RuntimeError("GitHub pull request files response was not a list")

            files.extend(item for item in response if isinstance(item, dict))
            if len(response) < per_page:
                break
            page += 1

        return files

    async def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, headers=self._headers(), timeout=30) as client:
            response = await client.post(path, json=payload)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _normalize_private_key(private_key: str) -> str:
        return private_key.replace("\\n", "\n")

    @classmethod
    def _build_app_jwt(cls, app_id: int, private_key: str) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": str(app_id)}
        return jwt.encode(payload, cls._normalize_private_key(private_key), algorithm="RS256")

    async def create_installation_token(self, *, app_id: int, private_key: str, installation_id: int) -> str:
        app_jwt = self._build_app_jwt(app_id, private_key)
        app_client = GitHubClient(token=app_jwt)
        response = await app_client.post_json(f"/app/installations/{installation_id}/access_tokens", {})
        token = response.get("token")
        if not token:
            raise RuntimeError("GitHub installation token response did not include a token")

        return token

    async def request_pull_reviewers(
        self,
        *,
        owner: str,
        repo: str,
        pull_number: int,
        reviewers: list[str],
    ) -> Any:
        return await self.post_json(
            f"/repos/{owner}/{repo}/pulls/{pull_number}/requested_reviewers",
            {"reviewers": reviewers},
        )

    async def create_pull_review(
        self,
        *,
        owner: str,
        repo: str,
        pull_number: int,
        event: str,
        body: str,
    ) -> Any:
        return await self.post_json(
            f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews",
            {"event": event, "body": body},
        )

    async def create_issue_comment(
        self,
        *,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> Any:
        return await self.post_json(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            {"body": body},
        )

    async def create_check_run(
        self,
        *,
        owner: str,
        repo: str,
        name: str,
        head_sha: str,
        conclusion: str,
        title: str,
        summary: str,
        details_url: str | None = None,
    ) -> Any:
        payload: dict[str, Any] = {
            "name": name,
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {"title": title, "summary": summary},
        }
        if details_url:
            payload["details_url"] = details_url

        return await self.post_json(f"/repos/{owner}/{repo}/check-runs", payload)