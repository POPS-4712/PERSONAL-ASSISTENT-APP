"""Unit tests for the service monitor's four-state logic.

The key behaviours:
* a service with no endpoint configured for this environment -> not_configured
  (NOT offline), and it never drags the global state to "degraded";
* a configured service that does not answer -> offline -> degraded;
* postgres is judged by the app's real engine, not a separate host guess.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import services_probe as sp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fake_settings(monkeypatch):
    cfg = SimpleNamespace(
        n8n_base_url="http://n8n:5678",
        n8n_api_key="",
        playwright_base_url="",
        profile_base_url="",
    )
    monkeypatch.setattr(sp, "get_settings", lambda: cfg)
    return cfg


@pytest.fixture
def db_online(monkeypatch):
    monkeypatch.setattr(
        sp, "_check_database_sync", lambda: (True, 1.0, "SELECT 1 ok")
    )


def _stub_http(monkeypatch, *, ok: bool):
    async def fake(url, timeout=3.0):
        return (ok, 5.0 if ok else None, "HTTP 200" if ok else "ConnectError: nope")

    monkeypatch.setattr(sp, "_probe_http", fake)


@pytest.mark.anyio
async def test_nothing_configured_is_not_configured_not_offline(fake_settings, db_online):
    status = await sp.system_status()
    by_name = {s["name"]: s for s in status["services"]}

    assert by_name["postgres"]["status"] == "online"
    assert by_name["n8n"]["status"] == "not_configured"
    assert by_name["playwright"]["status"] == "not_configured"
    assert by_name["profile"]["status"] == "not_configured"

    # not_configured services do not make the platform look broken
    assert status["state"] == "operational"
    assert status["operational"] is True
    assert status["degraded_services"] == []
    assert sorted(status["not_configured_services"]) == ["n8n", "playwright", "profile"]


@pytest.mark.anyio
async def test_configured_and_reachable_is_online(fake_settings, db_online, monkeypatch):
    fake_settings.n8n_api_key = "k"
    fake_settings.playwright_base_url = "http://playwright:3000"
    fake_settings.profile_base_url = "http://profile:7777"
    _stub_http(monkeypatch, ok=True)

    status = await sp.system_status()
    by_name = {s["name"]: s for s in status["services"]}

    assert by_name["n8n"]["status"] == "online"
    assert by_name["playwright"]["status"] == "online"
    assert by_name["profile"]["status"] == "online"
    assert status["state"] == "operational"


@pytest.mark.anyio
async def test_configured_but_down_is_offline_and_degraded(fake_settings, db_online, monkeypatch):
    fake_settings.n8n_api_key = "k"
    _stub_http(monkeypatch, ok=False)

    status = await sp.system_status()
    by_name = {s["name"]: s for s in status["services"]}

    assert by_name["n8n"]["status"] == "offline"
    assert by_name["n8n"]["online"] is False
    assert status["state"] == "degraded"
    assert "n8n" in status["degraded_services"]
    # playwright/profile still unconfigured -> not in degraded
    assert "playwright" not in status["degraded_services"]


@pytest.mark.anyio
async def test_database_down_is_degraded(fake_settings, monkeypatch):
    monkeypatch.setattr(
        sp, "_check_database_sync", lambda: (False, None, "OperationalError: boom")
    )
    status = await sp.system_status()
    by_name = {s["name"]: s for s in status["services"]}

    assert by_name["postgres"]["status"] == "offline"
    assert status["operational"] is False
    assert status["state"] == "degraded"
    assert "postgres" in status["degraded_services"]


@pytest.mark.anyio
async def test_probe_target_carries_no_secret(fake_settings, db_online):
    status = await sp.system_status()
    for s in status["services"]:
        assert "://" not in s["target"] or "@" not in s["target"]
    assert next(s for s in status["services"] if s["name"] == "postgres")["target"] == "application database"
