"""_clientip: X-Forwarded-For must not be trusted unless a trusted proxy set it."""
from __future__ import annotations

import ipaddress
import types

import pytest

from app.core import ratelimit


class _FakeClient:
    def __init__(self, host: str):
        self.host = host


class _FakeRequest:
    def __init__(self, peer: str, headers: dict[str, str] | None = None):
        self.client = _FakeClient(peer)
        self.headers = headers or {}


def _settings_with(*cidrs: str):
    nets = [ipaddress.ip_network(c, strict=False) for c in cidrs]
    return types.SimpleNamespace(trusted_proxy_networks=nets)


@pytest.fixture(autouse=True)
def _no_trusted_proxies(monkeypatch):
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _settings_with())


def test_direct_client_xff_is_ignored(monkeypatch):
    req = _FakeRequest("203.0.113.9", {"x-forwarded-for": "1.2.3.4"})
    assert ratelimit._clientip(req) == "203.0.113.9"


def test_direct_client_without_xff_uses_peer():
    req = _FakeRequest("203.0.113.9")
    assert ratelimit._clientip(req) == "203.0.113.9"


def test_spoofed_xff_cannot_forge_another_bucket(monkeypatch):
    a = _FakeRequest("203.0.113.9", {"x-forwarded-for": "9.9.9.9"})
    b = _FakeRequest("203.0.113.9", {"x-forwarded-for": "8.8.8.8"})
    assert ratelimit._clientip(a) == ratelimit._clientip(b) == "203.0.113.9"


def test_trusted_proxy_xff_is_honoured(monkeypatch):
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _settings_with("127.0.0.1/32"))
    req = _FakeRequest("127.0.0.1", {"x-forwarded-for": "198.51.100.7"})
    assert ratelimit._clientip(req) == "198.51.100.7"


def test_trusted_proxy_chain_skips_trusted_hops(monkeypatch):
    monkeypatch.setattr(
        ratelimit, "get_settings", lambda: _settings_with("10.0.0.0/8", "127.0.0.1/32")
    )
    # client -> edge(198.51.100.7 spoof attempt) -> proxy 10.0.0.5 -> local 127.0.0.1
    req = _FakeRequest(
        "127.0.0.1", {"x-forwarded-for": "198.51.100.7, 203.0.113.1, 10.0.0.5"}
    )
    assert ratelimit._clientip(req) == "203.0.113.1"


def test_untrusted_peer_ignores_xff_even_if_it_contains_trusted(monkeypatch):
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _settings_with("10.0.0.0/8"))
    req = _FakeRequest("203.0.113.9", {"x-forwarded-for": "10.0.0.5"})
    assert ratelimit._clientip(req) == "203.0.113.9"
