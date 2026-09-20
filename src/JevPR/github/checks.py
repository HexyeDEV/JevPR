from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CheckRunResult:
    name: str
    conclusion: str
    summary: str