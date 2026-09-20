from __future__ import annotations

import logging
from dataclasses import dataclass

)


@dataclass(slots=True)
class EvaluationOutcome:
    decision: DecisionResult
    route: RoutingAction


class EvaluationService:
    def __init__(self, engine: JevDecisionEngine, policy: RoutingPolicy) -> None:
        self.engine = engine
        self.policy = policy

    async def evaluate(self, context: PullRequestContext) -> EvaluationOutcome:
        logger.info(
            "starting evaluation",
            extra={
                "repository": context.repository,
                "number": context.number,
                "changed_files": len(context.changed_files),
            },

        )
        return EvaluationOutcome(decision=decision, route=route)
