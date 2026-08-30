from __future__ import annotations


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "automation-center-backend"


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] == "ok"
    assert body["environment"] == "testing"
    assert body["status"] in ("ok", "degraded")


def test_openapi_served(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/api/system/status" in r.json()["paths"]


def test_metrics_are_real_numbers(client):
    r = client.get("/api/system/metrics")
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["cpu_percent"] <= 100.0
    assert body["memory_total_mb"] > 0
    assert body["disk_total_gb"] > 0


def test_system_status_probes_every_service(client):
    r = client.get("/api/system/status")
    assert r.status_code == 200
    body = r.json()
    names = {s["name"] for s in body["services"]}
    assert names == {"postgres", "n8n", "playwright", "profile"}
    # In the test sandbox none of them resolve -> degraded, but structured, not crashed.
    assert body["state"] in ("operational", "degraded")


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-request-id"]
