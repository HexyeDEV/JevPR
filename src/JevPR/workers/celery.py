from __future__ import annotations

import logging

from celery import Celery

from JevPR.config import settings


logger = logging.getLogger(__name__)

celery_app = Celery(
    "jevpr",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.task_routes = {"JevPR.workers.github.*": {"queue": "github"}}

logger.info("celery app configured", extra={"broker": settings.redis_url, "backend": settings.redis_url})