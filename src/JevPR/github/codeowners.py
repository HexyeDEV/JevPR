from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(slots=True)
class CodeOwnerRule:
    pattern: str
    owners: list[str]


def match_codeowners(path: str, rules: list[CodeOwnerRule]) -> list[str]:
    matched: list[str] = []
    file_path = PurePosixPath(path.lstrip("/"))

    for rule in rules:
        if PurePosixPath(rule.pattern) in file_path.parents or file_path.match(rule.pattern):
            matched.extend(rule.owners)

    return sorted(set(matched))