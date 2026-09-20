from fastapi.testclient import TestClient

import JevPR.api.webhook as webhook_module

from JevPR.main import create_app


def _signature(secret: str, payload: bytes) -> str:
    import hashlib
    import hmac

    return f"sha256={hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()}"


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_github_webhook_rejects_invalid_signature(monkeypatch) -> None:
    monkeypatch.setattr(webhook_module.settings, "github_webhook_secret", "secret")
    client = TestClient(create_app())

    response = client.post(
        "/webhooks/github",
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=bad"},
        json={"repository": {"full_name": "octo/repo"}, "pull_request": {"number": 1}},
    )

    assert response.status_code == 401


def test_github_webhook_accepts_valid_signature(monkeypatch) -> None:
    secret = "secret"
    monkeypatch.setattr(webhook_module.settings, "github_webhook_secret", secret)
    client = TestClient(create_app())
    payload = {"repository": {"full_name": "octo/repo"}, "pull_request": {"number": 1}}
    body = b'{"repository":{"full_name":"octo/repo"},"pull_request":{"number":1}}'

    response = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _signature(secret, body),
        },
        content=body,
    )

    assert response.status_code == 200