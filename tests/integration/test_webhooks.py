from fastapi.testclient import TestClient

import JevPR.api.webhook as webhook_module
from JevPR.decisions.models import DecisionEvidence, DecisionResult, RiskSignals
from JevPR.decisions.policy import RoutingAction
from JevPR.services.pull_request import _build_route_comment

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


def test_github_webhook_ignores_non_review_worthy_pr_action(monkeypatch) -> None:
    secret = "secret"
    monkeypatch.setattr(webhook_module.settings, "github_webhook_secret", secret)
    client = TestClient(create_app())
    payload = {
        "action": "edited",
        "repository": {"full_name": "octo/repo"},
        "pull_request": {"number": 1, "title": "Update docs", "user": {"login": "alice"}},
    }
    body = b'{"action":"edited","repository":{"full_name":"octo/repo"},"pull_request":{"number":1,"title":"Update docs","user":{"login":"alice"}}}'

    response = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _signature(secret, body),
        },
        content=body,
    )

    assert response.status_code == 202


def test_github_webhook_ignores_pull_request_review_events(monkeypatch) -> None:
    secret = "secret"
    monkeypatch.setattr(webhook_module.settings, "github_webhook_secret", secret)
    client = TestClient(create_app())
    body = (
        b'{"action":"submitted","review":{"state":"approved","user":{"login":"jevpr-reviews[bot]"}},'
        b'"repository":{"full_name":"octo/repo"},'
        b'"pull_request":{"number":1,"title":"Update docs","user":{"login":"alice"}}}'
    )

    response = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "pull_request_review",
            "X-Hub-Signature-256": _signature(secret, body),
        },
        content=body,
    )

    assert response.status_code == 202


def test_github_webhook_applies_routed_action(monkeypatch) -> None:
    secret = "secret"
    monkeypatch.setattr(webhook_module.settings, "github_webhook_secret", secret)

    applied_routes: list[dict[str, object]] = []

    async def _fake_apply(payload, context, route, decision):
        applied_routes.append(
            {
                "repository": context.repository,
                "number": context.number,
                "action": route.action,
                "reviewers": list(route.reviewers),
            }
        )

    monkeypatch.setattr("JevPR.services.pull_request._apply_route_to_github", _fake_apply)

    client = TestClient(create_app())
    payload = {
        "action": "opened",
        "repository": {"full_name": "octo/repo"},
        "installation": {"id": 12345},
        "pull_request": {
            "number": 1,
            "title": "Update docs",
            "user": {"login": "alice"},
            "base": {"ref": "main"},
            "head": {"ref": "feature/docs"},
            "labels": [],
        },
    }
    body = (
        b'{"action":"opened","repository":{"full_name":"octo/repo"},'
        b'"installation":{"id":12345},"pull_request":{"number":1,'
        b'"title":"Update docs","user":{"login":"alice"},"base":{"ref":"main"},'
        b'"head":{"ref":"feature/docs"},"labels":[]}}'
    )

    response = client.post(
        "/webhooks/github",
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": _signature(secret, body),
        },
        content=body,
    )

    assert response.status_code == 200
    assert applied_routes
    assert applied_routes[0]["repository"] == "octo/repo"


def test_route_comment_includes_jev_breakdown() -> None:
    decision = DecisionResult(
        signals=RiskSignals(
            breaking_api_change=1.0,
            security_sensitive=0.0,
            production_infra_change=0.5,
            model_risk=7.25,
        ),
        computed_risk=7.25,
        summary="Composite risk 7.25/10 derived from model risk 7.25/10, signal risk 6.25/10, and file risk 8.00/10. Most risky files: src/app.py (8.0/10).",
        evidence=[
            DecisionEvidence(key="breaking_api_change", value=1.0),
            DecisionEvidence(key="overall_risk", value=7.25),
        ],
    )
    route = RoutingAction(action="request_review", reviewers=["alice"])

    comment = _build_route_comment(decision, route)

    assert "JevPR routed this pull request as `request_review`." in comment
    assert "What Jev said:" in comment
    assert "Composite risk 7.25/10" in comment
    assert "Breaking API change: 1.00" in comment
    assert "Top risky files:" not in comment