"""Unit tests for the service monitor.

The behaviours that matter:

* a service with nothing configured for this environment -> ``not_configured``
  (NOT ``offline``), and it never drags the global state to "degraded";
* a configured service that does not answer -> ``offline`` -> degraded;
* n8n that answers /healthz but rejects the API key -> ``degraded``, not
  ``online``: the automations would fail, so a green light would be a lie;
* the profile is judged by real rows carrying real values, never by a table
  existing;
* Gemini is judged by the provider actually accepting the key, and the verdict
  is cached so the 5-second monitor loop does not burn provider quota;
* configuration written from the panel (database) beats the environment;
* no probe output ever contains a secret.
"""
from __future__ import annotations

import pytest

from app.models import Profile, User, UserRole, UserStatus
from app.services import service_config
from app.services import services_probe as sp

pytestmark = pytest.mark.anyio

_COMPLETE_CONFIG = {
    "sector": "tecnologia",
    "ubicacion": "Barcelona",
    "intereses": ["ia", "automatizacion"],
    "preferencias_laborales": ["remoto"],
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, session_factory):
    """Point the DB-backed probes at the test database and clear caches."""
    monkeypatch.setattr(sp, "_session_factory", lambda: session_factory)
    monkeypatch.setattr(sp, "_check_database_sync", lambda: (True, 1.0, "SELECT 1 ok"))
    sp.reset_gemini_cache()
    yield
    sp.reset_gemini_cache()


@pytest.fixture
def env_unset(monkeypatch):
    """No service configured through the environment."""
    from types import SimpleNamespace

    cfg = SimpleNamespace(
        n8n_base_url="",
        n8n_api_key="",
        playwright_base_url="",
        profile_base_url="",
        gemini_api_key="",
        gemini_model="gemini-2.5-flash",
        gemini_verify_ttl_seconds=300.0,
    )
    monkeypatch.setattr(service_config, "get_settings", lambda: cfg)
    monkeypatch.setattr(sp, "get_settings", lambda: cfg)
    return cfg


def stub_http(monkeypatch, routes: dict[str, tuple[int | None, float | None, str]]):
    """Fake `_probe_http`, matched by substring so tests stay readable.

    Records every call so a test can assert the provider was *not* called again.
    """
    calls: list[str] = []

    async def fake(url, *, headers=None, timeout=sp._HTTP_TIMEOUT):
        calls.append(url)
        for fragment, response in routes.items():
            if fragment in url:
                return response
        return (None, None, "ConnectError: no route")

    monkeypatch.setattr(sp, "_probe_http", fake)
    return calls


def make_user(db) -> User:
    user = User(
        email="probe@example.com",
        username="probe",
        password_hash="x",
        role=UserRole.admin,
        status=UserStatus.active,
    )
    db.add(user)
    db.commit()
    return user


def by_name(status: dict) -> dict:
    return {s["name"]: s for s in status["services"]}


# ------------------------------------------------------------- baseline ------


async def test_nothing_configured_is_not_configured_not_offline(env_unset):
    status = await sp.system_status()
    services = by_name(status)

    assert services["postgres"]["status"] == "online"
    assert services["n8n"]["status"] == "not_configured"
    assert services["playwright"]["status"] == "not_configured"
    assert services["gemini"]["status"] == "not_configured"
    # no profile rows exist -> not configured, and that is not an error either
    assert services["profile"]["status"] == "not_configured"

    # not_configured services must not make the platform look broken
    assert status["operational"] is True
    assert status["state"] == "operational"
    assert status["degraded_services"] == []
    assert sorted(status["not_configured_services"]) == [
        "gemini",
        "n8n",
        "playwright",
        "profile",
    ]


async def test_unconfigured_services_say_what_is_missing(env_unset):
    services = by_name(await sp.system_status())
    assert "AC_N8N_BASE_URL" in services["n8n"]["detail"]
    assert "AC_N8N_API_KEY" in services["n8n"]["detail"]
    assert services["n8n"]["configured"] is False


async def test_database_down_is_degraded(env_unset, monkeypatch):
    monkeypatch.setattr(
        sp, "_check_database_sync", lambda: (False, None, "OperationalError: boom")
    )
    status = await sp.system_status()

    assert by_name(status)["postgres"]["status"] == "offline"
    assert status["operational"] is False
    assert "postgres" in status["degraded_services"]


# ------------------------------------------------------------------ n8n ------


async def test_n8n_reachable_and_key_accepted_is_online(env_unset, monkeypatch):
    env_unset.n8n_base_url = "https://n8n.example.com"
    env_unset.n8n_api_key = "secret-key-value"
    stub_http(monkeypatch, {"/healthz": (200, 12.0, "HTTP 200"), "/api/v1/workflows": (200, 20.0, "HTTP 200")})

    service = by_name(await sp.system_status())["n8n"]
    assert service["status"] == "online"
    assert service["online"] is True
    assert service["configured"] is True
    assert service["latency_ms"] is not None
    assert service["meta"]["api_key_valid"] is True


async def test_n8n_reachable_but_key_rejected_is_degraded(env_unset, monkeypatch):
    env_unset.n8n_base_url = "https://n8n.example.com"
    env_unset.n8n_api_key = "wrong-key"
    stub_http(monkeypatch, {"/healthz": (200, 12.0, "HTTP 200"), "/api/v1/workflows": (401, 9.0, "HTTP 401")})

    status = await sp.system_status()
    service = by_name(status)["n8n"]
    assert service["status"] == "degraded"
    assert service["meta"]["api_key_valid"] is False
    # a half-working integration counts as a fault, not as healthy
    assert "n8n" in status["degraded_services"]
    assert status["operational"] is False


async def test_n8n_configured_but_down_is_offline(env_unset, monkeypatch):
    env_unset.n8n_base_url = "https://n8n.example.com"
    env_unset.n8n_api_key = "k"
    stub_http(monkeypatch, {})  # nothing answers

    status = await sp.system_status()
    service = by_name(status)["n8n"]
    assert service["status"] == "offline"
    assert service["online"] is False
    assert "n8n" in status["degraded_services"]
    # playwright stays unconfigured -> still not a fault
    assert "playwright" not in status["degraded_services"]


# ----------------------------------------------------------- playwright ------


async def test_playwright_online_and_offline(env_unset, monkeypatch):
    env_unset.playwright_base_url = "https://scraper.example.com"
    stub_http(monkeypatch, {"/health": (200, 7.5, "HTTP 200")})
    assert by_name(await sp.system_status())["playwright"]["status"] == "online"

    stub_http(monkeypatch, {})
    assert by_name(await sp.system_status())["playwright"]["status"] == "offline"


# --------------------------------------------------------------- gemini ------


async def test_gemini_key_accepted_is_configured(env_unset, monkeypatch):
    env_unset.gemini_api_key = "AIza-test-key"
    stub_http(monkeypatch, {"generativelanguage": (200, 30.0, "HTTP 200")})

    service = by_name(await sp.system_status())["gemini"]
    assert service["status"] == "configured"
    assert service["online"] is True


async def test_gemini_key_rejected_is_invalid_not_offline(env_unset, monkeypatch):
    env_unset.gemini_api_key = "bad-key"
    stub_http(monkeypatch, {"generativelanguage": (403, 30.0, "HTTP 403")})

    status = await sp.system_status()
    service = by_name(status)["gemini"]
    assert service["status"] == "invalid"
    assert "gemini" in status["degraded_services"]


async def test_gemini_provider_unreachable_is_offline(env_unset, monkeypatch):
    env_unset.gemini_api_key = "AIza-test-key"
    stub_http(monkeypatch, {})
    assert by_name(await sp.system_status())["gemini"]["status"] == "offline"


async def test_gemini_verdict_is_cached_between_probes(env_unset, monkeypatch):
    env_unset.gemini_api_key = "AIza-test-key"
    calls = stub_http(monkeypatch, {"generativelanguage": (200, 30.0, "HTTP 200")})

    await sp.system_status()
    await sp.system_status()
    provider_calls = [c for c in calls if "generativelanguage" in c]
    assert len(provider_calls) == 1, "the monitor must not re-validate the key every tick"

    # a forced check bypasses the cache - that is what CHECK SERVICES does
    await sp.system_status(force=True)
    assert len([c for c in calls if "generativelanguage" in c]) == 2


async def test_gemini_cache_is_busted_by_a_key_change(env_unset, monkeypatch):
    env_unset.gemini_api_key = "first-key"
    calls = stub_http(monkeypatch, {"generativelanguage": (200, 30.0, "HTTP 200")})
    await sp.system_status()

    env_unset.gemini_api_key = "second-key"
    await sp.system_status()
    assert len([c for c in calls if "generativelanguage" in c]) == 2


# -------------------------------------------------------------- profile ------


async def test_profile_row_alone_is_not_configured(env_unset, db_session):
    """A row existing must not turn the tile green - the data has to be there."""
    user = make_user(db_session)
    db_session.add(Profile(user_id=user.id, name="Vacio", configuration={}, is_primary=True))
    db_session.commit()

    service = by_name(await sp.system_status())["profile"]
    assert service["status"] == "not_configured"
    assert "missing" in service["detail"]
    assert service["meta"]["profile_count"] == 1


async def test_profile_with_minimum_data_is_configured(env_unset, db_session):
    user = make_user(db_session)
    db_session.add(
        Profile(user_id=user.id, name="Alex", configuration=dict(_COMPLETE_CONFIG), is_primary=True)
    )
    db_session.commit()

    service = by_name(await sp.system_status())["profile"]
    assert service["status"] == "configured"
    assert service["online"] is True
    assert service["meta"]["complete_profiles"] == 1


async def test_empty_multiselect_does_not_count_as_filled(env_unset, db_session):
    user = make_user(db_session)
    config = dict(_COMPLETE_CONFIG, intereses=[])
    db_session.add(Profile(user_id=user.id, name="Alex", configuration=config, is_primary=True))
    db_session.commit()

    service = by_name(await sp.system_status())["profile"]
    assert service["status"] == "not_configured"
    assert "intereses" in service["detail"]


async def test_inactive_profile_does_not_count(env_unset, db_session):
    user = make_user(db_session)
    db_session.add(
        Profile(
            user_id=user.id,
            name="Alex",
            configuration=dict(_COMPLETE_CONFIG),
            is_primary=False,
            is_active=False,
        )
    )
    db_session.commit()

    assert by_name(await sp.system_status())["profile"]["status"] == "not_configured"


# ------------------------------------------------- database beats env --------


async def test_panel_configuration_overrides_the_environment(env_unset, db_session, monkeypatch):
    """The point of Phase 2: change the endpoint from the panel, no redeploy."""
    env_unset.n8n_base_url = "https://from-env.example.com"
    env_unset.n8n_api_key = "env-key"
    service_config.upsert(
        db_session, "n8n", base_url="https://from-panel.example.com", secret="panel-key"
    )
    probed: list[str] = stub_http(
        monkeypatch, {"/healthz": (200, 5.0, "HTTP 200"), "/api/v1/workflows": (200, 5.0, "HTTP 200")}
    )

    service = by_name(await sp.system_status())["n8n"]
    assert service["status"] == "online"
    assert service["target"] == "https://from-panel.example.com"
    assert service["meta"]["source"] == "database"
    assert all("from-env" not in url for url in probed)


async def test_disabled_service_reports_not_configured(env_unset, db_session, monkeypatch):
    env_unset.n8n_base_url = "https://n8n.example.com"
    env_unset.n8n_api_key = "k"
    service_config.upsert(db_session, "n8n", enabled=False)
    calls = stub_http(monkeypatch, {"/healthz": (200, 5.0, "HTTP 200")})

    service = by_name(await sp.system_status())["n8n"]
    assert service["status"] == "not_configured"
    assert calls == [], "a disabled service must not be contacted at all"


# ------------------------------------------------------------- secrets -------


async def test_probe_output_never_contains_a_secret(env_unset, db_session, monkeypatch):
    secret = "super-secret-n8n-key"
    env_unset.n8n_base_url = "https://n8n.example.com"
    env_unset.n8n_api_key = secret
    env_unset.gemini_api_key = "super-secret-gemini-key"
    stub_http(
        monkeypatch,
        {
            "/healthz": (200, 5.0, "HTTP 200"),
            "/api/v1/workflows": (401, 5.0, "HTTP 401"),
            "generativelanguage": (403, 5.0, "HTTP 403"),
        },
    )

    status = await sp.system_status()
    blob = repr(status)
    assert secret not in blob
    assert "super-secret-gemini-key" not in blob
    for service in status["services"]:
        assert "@" not in service["target"] or "://" not in service["target"]
    assert by_name(status)["postgres"]["target"] == "application database"
