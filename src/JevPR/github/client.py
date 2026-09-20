from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


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

    async def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, headers=self._headers(), timeout=30) as client:
            response = await client.post(path, json=payload)
            response.raise_for_status()
            return response.json()