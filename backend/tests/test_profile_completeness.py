"""Profile completeness (Phase 5).

The rule the dashboard depends on: a profile is "configured" only when it
carries the data the automations actually read. A row existing, or a
`configuration` full of empty selections, is NOT configured - marking it green
would send the Agenda/Laboral/Noticias workflows out with nothing to filter on.
"""
from __future__ import annotations

import pytest

from app.models import Profile, User, UserRole, UserStatus
from app.services import profiles as svc

COMPLETE = {
    "sector": "tecnologia",
    "ubicacion": "Barcelona",
    "intereses": ["ia"],
    "preferencias_laborales": ["remoto"],
}


@pytest.fixture
def user(db_session) -> User:
    row = User(
        email="p@example.com",
        username="pruser",
        password_hash="x",
        role=UserRole.admin,
        status=UserStatus.active,
    )
    db_session.add(row)
    db_session.commit()
    return row


def make_profile(db_session, user, config, **kw) -> Profile:
    row = Profile(
        user_id=user.id,
        name=kw.pop("name", "Perfil"),
        configuration=config,
        is_primary=kw.pop("is_primary", True),
        **kw,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_complete_profile(db_session, user):
    report = svc.profile_completeness(make_profile(db_session, user, dict(COMPLETE)))
    assert report["complete"] is True
    assert report["missing"] == []
    assert report["score"] == 1.0


def test_empty_configuration_is_incomplete(db_session, user):
    report = svc.profile_completeness(make_profile(db_session, user, {}))
    assert report["complete"] is False
    assert set(report["missing"]) == {"profesion", "ubicacion", "intereses", "preferencias"}
    assert report["score"] == 0.0


@pytest.mark.parametrize("empty", ["", "   ", [], [""], ["  "], None, {}])
def test_blank_values_do_not_count(db_session, user, empty):
    config = dict(COMPLETE, intereses=empty)
    report = svc.profile_completeness(make_profile(db_session, user, config))
    assert report["complete"] is False
    assert "intereses" in report["missing"]


def test_alternative_field_names_are_accepted(db_session, user):
    """A panel form writing plain Spanish names satisfies the same rule as the
    older modules.json dimension names - no migration needed."""
    config = {
        "profesion": "Ingeniero",
        "ubicacion": "Lleida",
        "intereses": ["automatizacion"],
        "preferencias": {"idioma": "es"},
    }
    assert svc.profile_completeness(make_profile(db_session, user, config))["complete"] is True


def test_objetivo_profesional_satisfies_profesion(db_session, user):
    config = dict(COMPLETE)
    del config["sector"]
    config["objetivo_profesional"] = "cambiar de sector"
    assert svc.profile_completeness(make_profile(db_session, user, config))["complete"] is True


def test_unnamed_profile_is_incomplete(db_session, user):
    report = svc.profile_completeness(make_profile(db_session, user, dict(COMPLETE), name="   "))
    assert report["complete"] is False
    assert "name" in report["missing"]


def test_inactive_profile_is_incomplete(db_session, user):
    profile = make_profile(db_session, user, dict(COMPLETE), is_primary=False, is_active=False)
    report = svc.profile_completeness(profile)
    assert report["complete"] is False
    assert "active" in report["missing"]


# ------------------------------------------------------------ aggregates -----


def test_any_complete_profile_with_no_rows(db_session):
    report = svc.any_complete_profile(db_session)
    assert report == {"configured": False, "profile_count": 0, "detail": "no profile created yet"}


def test_any_complete_profile_reports_what_is_missing(db_session, user):
    make_profile(db_session, user, {"ubicacion": "Barcelona"})
    report = svc.any_complete_profile(db_session)
    assert report["configured"] is False
    assert "intereses" in report["detail"]
    assert report["profile_count"] == 1


def test_any_complete_profile_finds_the_good_one(db_session, user):
    make_profile(db_session, user, {}, name="Vacio")
    make_profile(db_session, user, dict(COMPLETE), name="Bueno", is_primary=False)
    report = svc.any_complete_profile(db_session)
    assert report["configured"] is True
    assert report["complete_profiles"] == 1
    assert report["profile_count"] == 2


def test_aggregate_report_leaks_no_profile_content(db_session, user):
    """The health endpoint is instance-wide, so it must never carry PII."""
    make_profile(db_session, user, dict(COMPLETE, ubicacion="Calle Falsa 123"))
    assert "Calle Falsa" not in repr(svc.any_complete_profile(db_session))


# ------------------------------------------------------------------ API ------


_PASSWORD = "Correct9Horse"


def _login(client) -> str:
    client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "username": "admin", "password": _PASSWORD},
    )
    r = client.post("/api/auth/login", json={"identifier": "admin", "password": _PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_completeness_endpoint_walks_the_user_from_empty_to_ready(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/profiles/completeness", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False
    assert body["profile_count"] == 0
    assert body["required_fields"] == ["profesion", "ubicacion", "intereses", "preferencias"]

    client.post(
        "/api/profiles",
        headers=headers,
        json={"name": "Alex", "configuration": COMPLETE, "make_primary": True},
    )
    body = client.get("/api/profiles/completeness", headers=headers).json()
    assert body["configured"] is True
    assert body["best"]["complete"] is True


def test_completeness_endpoint_requires_auth(client):
    assert client.get("/api/profiles/completeness").status_code == 401
