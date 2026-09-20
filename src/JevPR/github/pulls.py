from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PullRequestMetadata:
    number: int
    repository: str
    title: str
    branch: str
    base_branch: str
    author: str
    changed_files: list[str]