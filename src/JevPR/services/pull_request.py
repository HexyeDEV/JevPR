from __future__ import annotations

import logging

import httpx

from JevPR.config import settings
from JevPR.decisions.context import ChangedFile, PullRequestContext
from JevPR.decisions.engine import JevDecisionEngine
from JevPR.decisions.policy import RoutingAction, get_routing_policy
from JevPR.decisions.policy import RoutingPolicy, default_policy
from JevPR.decisions.models import DecisionResult
from JevPR.github.client import GitHubClient
from JevPR.providers.jev import JevProvider
from JevPR.services.evaluation import EvaluationOutcome, EvaluationService


logger = logging.getLogger(__name__)

REVIEW_WORTHY_PR_ACTIONS = {"opened", "reopened", "synchronize", "ready_for_review"}


def _is_review_worthy_pull_request(payload: dict) -> bool:
    action = payload.get("action")
    if action in REVIEW_WORTHY_PR_ACTIONS:
        return True

    return False


def _split_repository_name(repository_name: str) -> tuple[str, str] | None:
    owner, separator, repo = repository_name.partition("/")
    if not separator or not owner or not repo:
        return None

    return owner, repo


async def _create_installation_client(payload: dict) -> tuple[str, str, GitHubClient] | None:
    installation_id = payload.get("installation", {}).get("id")
    repository_name = payload.get("repository", {}).get("full_name", "")
    repository_parts = _split_repository_name(repository_name)
    if installation_id is None or repository_parts is None:
        logger.warning(
            "github action skipped because installation or repository information is missing",
            extra={"installation_id": installation_id, "repository": repository_name},
        )
        return None

    if settings.github_app_id is None or settings.github_app_private_key is None:
        logger.warning("github action skipped because app credentials are not configured")
        return None

    owner, repo = repository_parts
    client = GitHubClient()
    installation_token = await client.create_installation_token(
        app_id=settings.github_app_id,
        private_key=settings.github_app_private_key,
        installation_id=installation_id,
    )
    return owner, repo, GitHubClient(token=installation_token)


async def _load_changed_files(payload: dict, github: GitHubClient, owner: str, repo: str) -> list[ChangedFile]:
    pull_number = payload.get("pull_request", {}).get("number", 0)
    file_entries = await github.list_pull_request_files(
        owner=owner,
        repo=repo,
        pull_number=pull_number,
    )
    changed_files = [
        ChangedFile(
            path=file.get("filename", ""),
            status=file.get("status", "modified"),
            additions=file.get("additions", 0),
            deletions=file.get("deletions", 0),
            diff=file.get("patch"),
        )
        for file in file_entries
    ]

    logger.info(
        "pull request files loaded",
        extra={
            "repository": payload.get("repository", {}).get("full_name", "unknown/repo"),
            "number": pull_number,
            "changed_files": len(changed_files),
        },
    )
    return changed_files


def _format_decision_breakdown(decision: DecisionResult) -> str:
    lines = [
        "What Jev said:",
        f"- Composite risk: {decision.computed_risk:.2f}/10",
        f"- Level: {decision.level.value}",
        f"- Assessment summary: {decision.summary}",
        "- Signals:",
        f"  - Breaking API change: {decision.signals.breaking_api_change:.2f}/1.0",
        f"  - Security sensitive: {decision.signals.security_sensitive:.2f}/1.0",
        f"  - Production infra change: {decision.signals.production_infra_change:.2f}/1.0",
        f"  - Model risk: {decision.signals.model_risk:.2f}/10",
    ]

    if decision.evidence:
        lines.append("- Evidence:")
        for item in decision.evidence:
            lines.append(f"  - {item.key}: {item.value}")

    top_files = decision.top_risky_files()
    if top_files:
        lines.append("- Top risky files:")
        for file_risk in top_files:
            lines.append(f"  - {file_risk.path}: {file_risk.score:.2f}/10")

    return "\n".join(lines)


def _build_route_comment(decision: DecisionResult, route: RoutingAction) -> str:
    route_summary = f"JevPR routed this pull request as `{route.action}`."
    if route.reviewers:
        route_summary = f"{route_summary} Reviewers: {', '.join(route.reviewers)}."
    if route.codeowners_only:
        route_summary = f"{route_summary} Codeowners only: yes."
    if route.check_name:
        route_summary = f"{route_summary} Check: {route.check_name}."

    return f"{route_summary}\n\n{_format_decision_breakdown(decision)}"


async def _apply_route_to_github(
    payload: dict,
    context: PullRequestContext,
    route: RoutingAction,
    decision: DecisionResult,
    github: GitHubClient | None = None,
    has_default_policy: bool = True
) -> None:
    if route.action == "noop":
        return

    if github is None:
        installation_client = await _create_installation_client(payload)
        if installation_client is None:
            return
        _, _, github = installation_client

    repository_name = payload.get("repository", {}).get("full_name", "")
    repository_parts = _split_repository_name(repository_name)
    if repository_parts is None:
        logger.warning(
            "github action skipped because repository information is missing",
            extra={"repository": repository_name},
        )
        return

    owner, repo = repository_parts

    route_summary = _build_route_comment(decision, route)

    if has_default_policy:
        route_summary = f"""{route_summary}
        
        *Note: This routing was determined by the default policy.*
        The repository does not have a custom routing configuration.

        Create one at `.github/jevpr.yml` in the repository to customize routing behavior.
        Configuration Template:

        ```yaml
        {settings.config_path.read_text(encoding="utf-8")}
        ```"""

    await github.create_issue_comment(
        owner=owner,
        repo=repo,
        issue_number=context.number,
        body=route_summary,
    )

    if route.action == "approve":
        await github.create_pull_review(
            owner=owner,
            repo=repo,
            pull_number=context.number,
            event="APPROVE",
            body=route_summary,
        )
    elif route.action == "request_review" and route.reviewers:
        try:
            await github.request_pull_reviewers(
                owner=owner,
                repo=repo,
                pull_number=context.number,
                reviewers=route.reviewers,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 422:
                logger.warning(
                    "github review request rejected by GitHub",
                    extra={
                        "repository": context.repository,
                        "number": context.number,
                        "reviewers": route.reviewers,
                        "status_code": exc.response.status_code,
                    },
                )
            else:
                raise
    elif route.action == "create_check":
        head_sha = payload.get("pull_request", {}).get("head", {}).get("sha")
        if not head_sha:
            logger.warning(
                "github check skipped because pull request head sha is missing",
                extra={"repository": context.repository, "number": context.number},
            )
            return

        check_name = route.check_name or "JevPR"
        await github.create_check_run(
            owner=owner,
            repo=repo,
            name=check_name,
            head_sha=head_sha,
            conclusion="neutral",
            title=check_name,
            summary=route_summary,
            details_url=payload.get("pull_request", {}).get("html_url"),
        )

    logger.info(
        "github action applied",
        extra={
            "repository": context.repository,
            "number": context.number,
            "action": route.action,
        },
    )


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

    installation_client = await _create_installation_client(payload)
    changed_files: list[ChangedFile] = []
    github_client: GitHubClient | None = None
    if installation_client is not None:
        owner, repo, github_client = installation_client
        changed_files = await _load_changed_files(payload, github_client, owner, repo)

    context.changed_files = changed_files

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
    policy: RoutingPolicy = await get_routing_policy(
        owner=context.repository.split("/")[0],
        repo=context.repository.split("/")[1]
    )
    has_default_policy = policy == default_policy()
    service = EvaluationService(engine=engine, policy=policy)
    outcome: EvaluationOutcome = await service.evaluate(context)
    await _apply_route_to_github(payload, context, outcome.route, outcome.decision, github_client, has_default_policy)
    logger.info(
        "pull request routed",
        extra={
            "repository": context.repository,
            "number": context.number,
            "route_action": outcome.route.action,
        },
    )
    return {"status": "processed", "action": outcome.route.action}