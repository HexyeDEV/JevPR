from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ChangedFile:
    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    diff: str | None = None


@dataclass(slots=True)
class PullRequestContext:
    repository: str
    number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    changed_files: list[ChangedFile] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)