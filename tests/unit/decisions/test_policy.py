from JevPR.config import ActionConfig, RoutingConfig
from JevPR.decisions.models import DecisionLevel, DecisionResult
from JevPR.decisions.policy import RoutingPolicy


def test_policy_resolves_configured_action() -> None:
    policy = RoutingPolicy(
        RoutingConfig(actions={"LOW": ActionConfig(action="approve", reviewers=["alice"])})
    )

    route = policy.resolve(DecisionResult(level=DecisionLevel.LOW, confidence=1.0, rationale="ok"))

    assert route.action == "approve"
    assert route.reviewers == ["alice"]