from __future__ import annotations

from abc import ABC, abstractmethod

from JevPR.decisions.context import PullRequestContext
from JevPR.decisions.models import DecisionResult


class DecisionProvider(ABC):
    @abstractmethod
    async def evaluate(self, context: PullRequestContext) -> DecisionResult:
        raise NotImplementedError