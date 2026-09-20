from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ReviewRequest:
    reviewers: list[str] = field(default_factory=list)
    approve: bool = False
    check_name: str | None = None