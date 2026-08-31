from __future__ import annotations

import logging
import uuid

import pytest
from starlette.websockets import WebSocketDisconnect

PW = "Sup3rSecret!!"


@pytest.fixture
def token(client):
    def make():
        r = client.post(
            "/api/auth/register",
            json={
                "email": f"{uuid.uuid4().hex}@example.com",
                "username": "u" + uuid.uuid4().hex[:10],
                "password": PW,
            },
        )
        assert r.status_code == 201, r.text
        return r.json()["access_token"]

    return make


def test_rest_metrics_and_status_still_work(client):
    assert client.get("/api/system/metrics").status_code == 200
    assert client.get("/api/system/status").status_code == 200


def test_ws_monitor_rejects_missing_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/monitor"):
            pass


def test_ws_monitor_rejects_bad_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/monitor?token=not-a-jwt"):
            pass


def test_ws_monitor_streams_structured_events(client, token):
    t = token()
    with client.websocket_connect(f"/ws/monitor?token={t}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["channel"] == "monitor"
        seen_types = set()
        for _ in range(6):
            evt = ws.receive_json()
            seen_types.add(evt["type"])
            assert "timestamp" in evt
        assert "system.metrics" in seen_types
        assert "service.status" in seen_types


def test_ws_monitor_uses_one_shared_collector(client, token):
    from app.services.monitor import hub

    t = token()
    with client.websocket_connect(f"/ws/monitor?token={t}") as a:
        a.receive_json()
        with client.websocket_connect(f"/ws/monitor?token={t}") as b:
            b.receive_json()
            assert hub.subscriber_count == 2  # two clients, still one hub


def test_ws_logs_streams_and_scrubs_secrets(client, token):
    from app.services.logbus import bus

    bus._ring.clear()
    marker = f"marker-{uuid.uuid4().hex}"
    logging.getLogger("test.emitter").warning(
        f"{marker} connecting with api_key=SUPERSECRETVALUE and token=abc123"
    )
    t = token()
    with client.websocket_connect(f"/ws/logs?token={t}&level=INFO") as ws:
        assert ws.receive_json()["type"] == "hello"
        for _ in range(60):
            evt = ws.receive_json()
            if evt["type"] == "log" and marker in evt["message"]:
                assert "SUPERSECRETVALUE" not in evt["message"]
                assert "api_key=***" in evt["message"]
                assert evt["level"] == "WARNING"
                assert evt["source"] == "test.emitter"
                return
    pytest.fail("scrubbed log line never arrived on the stream")


def test_ws_logs_rejects_missing_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/logs"):
            pass


def _mint_token(sub: str, *, exp_in: int) -> str:
    import datetime as dt

    import jwt

    from app.config import get_settings

    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    return jwt.encode(
        {
            "sub": sub,
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(now.timestamp()) + exp_in,
        },
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )


def test_ws_monitor_rejects_expired_token(client, db_session):
    from app.models import User

    client.post(
        "/api/auth/register",
        json={"email": "exp@example.com", "username": "expuser", "password": PW},
    )
    uid = str(db_session.query(User).filter(User.username == "expuser").first().id)
    expired = _mint_token(uid, exp_in=-10)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/monitor?token={expired}"):
            pass


def test_ws_monitor_closes_when_token_expires_mid_stream(client, db_session):
    from app.models import User

    client.post(
        "/api/auth/register",
        json={"email": "exp2@example.com", "username": "expuser2", "password": PW},
    )
    uid = str(db_session.query(User).filter(User.username == "expuser2").first().id)
    short = _mint_token(uid, exp_in=2)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/monitor?token={short}") as ws:
            ws.receive_json()  # hello
            for _ in range(50):
                ws.receive_json()


def test_rest_logs_endpoint_requires_auth_and_filters(client, token):
    assert client.get("/api/logs").status_code == 401
    t = token()
    logging.getLogger("test.rest").error("a distinctive error line")
    r = client.get("/api/logs?level=ERROR&limit=50", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert any("distinctive error line" in e["message"] for e in r.json()["data"])
