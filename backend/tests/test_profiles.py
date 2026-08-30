from __future__ import annotations

import uuid

import pytest

PW = "Sup3rSecret!!"


@pytest.fixture
def auth_headers(client):
    """Register a fresh user, return (headers, user_dict)."""

    def make():
        email = f"{uuid.uuid4().hex}@example.com"
        username = "u" + uuid.uuid4().hex[:10]
        r = client.post(
            "/api/auth/register", json={"email": email, "username": username, "password": PW}
        )
        assert r.status_code == 201, r.text
        tok = r.json()
        return {"Authorization": f"Bearer {tok['access_token']}"}, tok["user"]

    return make


def test_dimensions_endpoint_lists_all(client):
    r = client.get("/api/profiles/dimensions")
    assert r.status_code == 200
    dims = r.json()["dimensions"]
    for expected in ("formacion", "sector", "ubicacion", "marca_personal", "automatizaciones"):
        assert expected in dims


def test_create_first_profile_is_primary(client, auth_headers):
    h, _ = auth_headers()
    r = client.post("/api/profiles", json={"name": "Ingeniería", "configuration": {"idioma": "es"}}, headers=h)
    assert r.status_code == 201
    assert r.json()["is_primary"] is True


def test_configuration_accepts_unknown_keys(client, auth_headers):
    h, _ = auth_headers()
    cfg = {"formacion": ["x"], "brand_new_dimension_2027": {"a": 1}}
    r = client.post("/api/profiles", json={"name": "P", "configuration": cfg}, headers=h)
    assert r.status_code == 201
    assert r.json()["configuration"]["brand_new_dimension_2027"] == {"a": 1}


def test_full_crud_cycle(client, auth_headers):
    h, _ = auth_headers()
    pid = client.post("/api/profiles", json={"name": "A"}, headers=h).json()["id"]
    client.post("/api/profiles", json={"name": "B"}, headers=h)

    assert len(client.get("/api/profiles", headers=h).json()) == 2
    assert client.get(f"/api/profiles/{pid}", headers=h).json()["name"] == "A"

    up = client.patch(f"/api/profiles/{pid}", json={"description": "eng track"}, headers=h)
    assert up.json()["description"] == "eng track"

    dup = client.post(f"/api/profiles/{pid}/duplicate", headers=h)
    assert dup.status_code == 201
    assert dup.json()["name"] == "A (copia)"
    assert dup.json()["is_primary"] is False

    assert client.delete(f"/api/profiles/{pid}", headers=h).status_code == 200
    assert client.get(f"/api/profiles/{pid}", headers=h).status_code == 404


def test_primary_switch_is_exclusive(client, auth_headers):
    h, _ = auth_headers()
    a = client.post("/api/profiles", json={"name": "A"}, headers=h).json()["id"]
    b = client.post("/api/profiles", json={"name": "B"}, headers=h).json()["id"]
    client.post(f"/api/profiles/{b}/primary", headers=h)
    rows = {p["id"]: p["is_primary"] for p in client.get("/api/profiles", headers=h).json()}
    assert rows[b] is True and rows[a] is False


def test_cannot_deactivate_primary(client, auth_headers):
    h, _ = auth_headers()
    a = client.post("/api/profiles", json={"name": "A"}, headers=h).json()["id"]
    r = client.post(f"/api/profiles/{a}/deactivate", headers=h)
    assert r.status_code == 409


def test_deleting_primary_promotes_another(client, auth_headers):
    h, _ = auth_headers()
    a = client.post("/api/profiles", json={"name": "A"}, headers=h).json()["id"]
    b = client.post("/api/profiles", json={"name": "B"}, headers=h).json()["id"]
    client.delete(f"/api/profiles/{a}", headers=h)
    rows = {p["id"]: p["is_primary"] for p in client.get("/api/profiles", headers=h).json()}
    assert rows[b] is True


def test_user_cannot_see_or_touch_another_users_profile(client, auth_headers):
    h1, _ = auth_headers()
    h2, _ = auth_headers()
    pid = client.post("/api/profiles", json={"name": "secret"}, headers=h1).json()["id"]

    # user 2: every access path is a 404, not a 403 (no existence leak)
    assert client.get(f"/api/profiles/{pid}", headers=h2).status_code == 404
    assert client.patch(f"/api/profiles/{pid}", json={"name": "hijack"}, headers=h2).status_code == 404
    assert client.delete(f"/api/profiles/{pid}", headers=h2).status_code == 404
    assert client.post(f"/api/profiles/{pid}/primary", headers=h2).status_code == 404
    assert client.post(f"/api/profiles/{pid}/duplicate", headers=h2).status_code == 404

    # user 2's list never includes user 1's rows
    assert client.get("/api/profiles", headers=h2).json() == []
    # and user 1 still owns it, untouched
    assert client.get(f"/api/profiles/{pid}", headers=h1).json()["name"] == "secret"


def test_profiles_require_auth(client):
    assert client.get("/api/profiles").status_code == 401
    assert client.post("/api/profiles", json={"name": "x"}).status_code == 401
