from __future__ import annotations

import logging
from dataclasses import dataclass, field

from JevPR.config import ActionConfig, RoutingConfig
from JevPR.decisions.models import DecisionLevel, DecisionResult, RiskSignals


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RoutingAction:
    action: str
    reviewers: list[str] = field(default_factory=list)
    check_name: str | None = None
    codeowners_only: bool = False


class RoutingPolicy:
    def __init__(self, config: RoutingConfig) -> None:
        self.config = config

    def resolve(self, decision: DecisionResult) -> RoutingAction:
        action_config = self.config.actions.get(decision.level.value)
        if action_config is None:
            logger.info("no routing action configured for decision level", extra={"level": decision.level.value})
            return RoutingAction(action="noop")

        logger.info(
            "routing action resolved",
            extra={
                "level": decision.level.value,
                "action": action_config.action,
                "reviewers": action_config.reviewers,
                "check_name": action_config.check_name,
            },
        )
        return self._convert(action_config)

    def _convert(self, config: ActionConfig) -> RoutingAction:
        return RoutingAction(
            action=config.action,
            reviewers=config.reviewers,
            check_name=config.check_name,
            codeowners_only=config.codeowners_only,
        )


def default_policy() -> RoutingPolicy:
    from JevPR.config import settings

    return RoutingPolicy(settings.load_routing_config())


def summarize_route(level: DecisionLevel, policy: RoutingPolicy) -> RoutingAction:
    score_map = {DecisionLevel.LOW: 2.0, DecisionLevel.NORMAL: 5.0, DecisionLevel.SPECIALIST: 8.5}
    return policy.resolve(
        DecisionResult(
            signals=RiskSignals(0.0, 0.0, 0.0, score_map[level]),
            computed_risk=score_map[level],
        )
    )