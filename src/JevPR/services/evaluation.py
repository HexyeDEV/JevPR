from __future__ import annotations

import logging

from JevPR.decisions.context import PullRequestContext
from JevPR.decisions.engine import JevDecisionEngine
from JevPR.decisions.policy import RoutingAction, RoutingPolicy


logger = logging.getLogger(__name__)


class EvaluationService:
    def __init__(self, engine: JevDecisionEngine, policy: RoutingPolicy) -> None:
        self.engine = engine
        self.policy = policy

    async def evaluate(self, context: PullRequestContext) -> RoutingAction:
        logger.info(
            "starting evaluation",
            extra={
                "repository": context.repository,
                "number": context.number,
                "changed_files": len(context.changed_files),
            },
        )
        decision = await self.engine.evaluate(context)
        logger.info(
            "decision evaluated",
            extra={
                "repository": context.repository,
                "number": context.number,
                "computed_risk": decision.computed_risk,
                "level": decision.level.value,
                "top_files": [file_risk.path for file_risk in decision.top_risky_files()],
            },
        )
        route = self.policy.resolve(decision)
        logger.info(
            "routing resolved",
            extra={
                "repository": context.repository,
                "number": context.number,
                "action": route.action,
                "reviewers": route.reviewers,
                "codeowners_only": route.codeowners_only,
            },
        )
        return route