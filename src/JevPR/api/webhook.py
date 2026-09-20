from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from JevPR.config import settings
from JevPR.services.pull_request import handle_pull_request_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)
SUPPORTED_GITHUB_EVENTS = {"pull_request"}


def _verify_github_signature(body: bytes, signature_header: str | None) -> None:
    secret = settings.github_webhook_secret
    if not secret:
        logger.debug("github webhook signature verification skipped because no secret is configured")
        return

    if not signature_header:
        logger.warning("github webhook rejected: missing signature header")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing signature")

    try:
        algorithm, signature = signature_header.split("=", 1)
    except ValueError as exc:
        logger.warning("github webhook rejected: invalid signature format")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signature") from exc

    if algorithm != "sha256":
        logger.warning("github webhook rejected: unsupported signature algorithm %s", algorithm)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unsupported signature")

    expected_signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        logger.warning("github webhook rejected: signature mismatch")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signature")


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict[str, str]:
    body = await request.body()
    _verify_github_signature(body, x_hub_signature_256)

    payload = await request.json()
    logger.info(
        "github webhook received",
        extra={"event": x_github_event, "payload_size": len(body)},
    )

    if x_github_event not in SUPPORTED_GITHUB_EVENTS:
        logger.info("github webhook ignored", extra={"event": x_github_event})
        raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail="ignored event")

    background_tasks.add_task(handle_pull_request_webhook, event_type=x_github_event, payload=payload)
    logger.info("github webhook accepted for background processing", extra={"event": x_github_event})
    return {"status": "accepted"}