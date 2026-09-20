from __future__ import annotations

from abc import ABC, abstractmethod

from JevPR.decisions.context import PullRequestContext
from JevPR.decisions.models import DecisionResult
from JevPR.providers.base import DecisionProvider


class DecisionEngine(ABC):
    @abstractmethod
    async def evaluate(self, context: PullRequestContext) -> DecisionResult:
        raise NotImplementedError


class JevDecisionEngine(DecisionEngine):
    def __init__(self, provider: DecisionProvider) -> None:
        self.provider = provider

    async def evaluate(self, context: PullRequestContext) -> DecisionResult:
        return await self.provider.evaluate(context)