from __future__ import annotations

import uuid

import pytest

from app.core import crypto

PW = "Sup3rSecret!!"


@pytest.fixture
def auth_headers(client):
    def make():
        email = f"{uuid.uuid4().hex}@example.com"
        username = "u" + uuid.uuid4().hex[:10]
        r = client.post(
            "/api/auth/register", json={"email": email, "username": username, "password": PW}
        )
        assert r.status_code == 201, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return make


SECRET = {"api_key": "sk-proj-ABCDEFGHIJKLMNOP8F3A"}


def _create(client, h, **over):
    body = {
        "provider": over.get("provider", "openai"),
        "name": over.get("name", "Cred-" + uuid.uuid4().hex[:6]),
        "type": over.get("type", "api_key"),
        "secret": over.get("secret", SECRET),
        "meta": over.get("meta", {}),
    }
    return client.post("/api/credentials", json=body, headers=h)


# 1. a credential can be saved
def test_credential_can_be_saved(client, auth_headers):
    h = auth_headers()
    r = _create(client, h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["provider"] == "openai"
    assert body["status"] == "untested"
    assert body["hint"] == "…8F3A"


# 2. it decrypts internally for an authorised server-side consumer
def test_secret_decrypts_internally(client, auth_headers, db_session):
    from app.models import User
    from app.services import credentials as svc

    h = auth_headers()
    cid = _create(client, h).json()["id"]
    # find the owning user
    user = db_session.query(User).order_by(User.created_at.desc()).first()
    secret = svc.reveal_secret(
        db_session, user.id, uuid.UUID(cid), requested_by="test-runner"
    )
    assert secret == SECRET


# 3. the API never returns the secret
def test_api_never_returns_secret(client, auth_headers):
    h = auth_headers()
    cid = _create(client, h).json()["id"]
    for resp in (
        client.get("/api/credentials", headers=h),
        client.get(f"/api/credentials/{cid}", headers=h),
    ):
        blob = resp.text
        assert "sk-proj-ABCDEFGHIJKLMNOP8F3A" not in blob
        assert "encrypted_data" not in blob
        assert "ABCDEFGHIJKLMNOP" not in blob


# 4. another user cannot access it
def test_other_user_cannot_access(client, auth_headers):
    h1 = auth_headers()
    h2 = auth_headers()
    cid = _create(client, h1).json()["id"]
    assert client.get(f"/api/credentials/{cid}", headers=h2).status_code == 404
    assert client.patch(f"/api/credentials/{cid}", json={"name": "x"}, headers=h2).status_code == 404
    assert client.delete(f"/api/credentials/{cid}", headers=h2).status_code == 404
    assert client.post(f"/api/credentials/{cid}/test", headers=h2).status_code == 404
    assert client.get("/api/credentials", headers=h2).json() == []


# 5. without the master key, ciphertext cannot be decrypted
def test_without_master_key_cannot_decrypt(client, auth_headers, db_session, monkeypatch):
    from app.models import Credential

    h = auth_headers()
    cid = _create(client, h).json()["id"]
    row = db_session.get(Credential, uuid.UUID(cid))
    blob = row.encrypted_data
    assert isinstance(blob, (bytes, bytearray)) and b"sk-proj" not in blob

    monkeypatch.setattr(crypto, "_keys", lambda: [])
    crypto.reset_cache()
    try:
        with pytest.raises(crypto.CipherNotConfigured):
            crypto.decrypt_secret(blob)
    finally:
        crypto.reset_cache()


# 6. the secret does not appear in logs
def test_secret_not_in_logs(client, auth_headers, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    h = auth_headers()
    cid = _create(client, h).json()["id"]
    client.patch(
        f"/api/credentials/{cid}",
        json={"secret": {"api_key": "sk-rotated-SENSITIVE-999"}},
        headers=h,
    )
    client.post(f"/api/credentials/{cid}/test", headers=h)
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "sk-proj-ABCDEFGHIJKLMNOP8F3A" not in joined
    assert "sk-rotated-SENSITIVE-999" not in joined


def test_store_status_endpoint(client, auth_headers):
    r = client.get("/api/credentials/store-status")
    assert r.status_code == 200
    assert r.json()["configured"] is True


def test_meta_strips_secret_looking_keys(client, auth_headers):
    h = auth_headers()
    r = _create(client, h, meta={"test_url": "https://x/y", "api_key": "leak", "password": "leak"})
    m = r.json()["meta"]
    assert m == {"test_url": "https://x/y"}


def test_audit_trail_written(client, auth_headers, db_session):
    from app.models import SystemEvent

    h = auth_headers()
    cid = _create(client, h).json()["id"]
    client.delete(f"/api/credentials/{cid}", headers=h)
    types = {e.type for e in db_session.query(SystemEvent).all()}
    assert {"credential.create", "credential.delete"} <= types
