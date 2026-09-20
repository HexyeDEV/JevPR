from __future__ import annotations

from JevPR.workers.celery import celery_app


@celery_app.task(name="JevPR.workers.github.process_webhook")
def process_webhook(event_type: str, payload: dict) -> dict[str, str]:
    return {"event_type": event_type, "status": "queued"}