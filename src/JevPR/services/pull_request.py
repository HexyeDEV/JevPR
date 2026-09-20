from __future__ import annotations

import logging

from JevPR.decisions.context import ChangedFile, PullRequestContext
from JevPR.decisions.engine import JevDecisionEngine
from JevPR.decisions.policy import RoutingPolicy, default_policy
from JevPR.providers.jev import JevProvider
from JevPR.services.evaluation import EvaluationService


logger = logging.getLogger(__name__)

REVIEW_WORTHY_PR_ACTIONS = {"opened", "reopened", "synchronize", "ready_for_review"}


def _is_review_worthy_pull_request(payload: dict) -> bool:
    action = payload.get("action")
    if action in REVIEW_WORTHY_PR_ACTIONS:
        return True

    return False


async def handle_pull_request_webhook(event_type: str, payload: dict) -> dict[str, str]:
    if event_type != "pull_request":
        logger.info("non pull_request event ignored in service layer", extra={"event": event_type})
        return {"status": "ignored"}

    if not _is_review_worthy_pull_request(payload):
        logger.info(
            "pull request webhook ignored because action is not review-worthy",
            extra={"action": payload.get("action")},
        )
        return {"status": "ignored"}

    context = PullRequestContext(
        repository=payload.get("repository", {}).get("full_name", "unknown/repo"),
        number=payload.get("pull_request", {}).get("number", 0),
        title=payload.get("pull_request", {}).get("title", ""),
        author=payload.get("pull_request", {}).get("user", {}).get("login", ""),
        base_branch=payload.get("pull_request", {}).get("base", {}).get("ref", "main"),
        head_branch=payload.get("pull_request", {}).get("head", {}).get("ref", ""),
        changed_files=[
            ChangedFile(
                path=file.get("filename", ""),
                status=file.get("status", "modified"),
                additions=file.get("additions", 0),
                deletions=file.get("deletions", 0),
                diff=file.get("patch"),
            )
            for file in payload.get("files", [])
        ],
        labels=[label.get("name", "") for label in payload.get("pull_request", {}).get("labels", [])],
    )

    logger.info(
        "pull request context built",
        extra={
            "repository": context.repository,
            "number": context.number,
            "action": payload.get("action"),
            "changed_files": len(context.changed_files),
            "labels": len(context.labels),
        },
    )

    engine = JevDecisionEngine(provider=JevProvider())
    policy: RoutingPolicy = default_policy()
    service = EvaluationService(engine=engine, policy=policy)
    route = await service.evaluate(context)
    logger.info(
        "pull request routed",
        extra={
            "repository": context.repository,
            "number": context.number,
            "route_action": route.action,
        },
    )
    return {"status": "processed", "action": route.action}