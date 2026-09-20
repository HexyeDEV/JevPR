from __future__ import annotations

import logging

from fastapi import FastAPI

from JevPR.api.health import router as health_router
from JevPR.api.webhook import router as webhook_router
from JevPR.config import settings
from JevPR.logging_utils import configure_logging


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    app = FastAPI(title="JevPR", version="0.1.0")
    app.state.settings = settings
    app.include_router(health_router)
    app.include_router(webhook_router)
    logger.info("application initialized", extra={"env": settings.env, "log_level": settings.log_level})
    return app


app = create_app()