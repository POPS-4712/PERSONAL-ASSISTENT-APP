"""SSRF guard: app/core/ssrf.py and its use by the credential-test feature."""
from __future__ import annotations

import ipaddress

import httpx
import pytest

from app.core import ssrf
from app.core.ssrf import BlockedRequestError, assert_public_url, guarded_get

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _fake_resolver(mapping: dict[str, list[str]]):
    def resolve(host: str):
        if host not in mapping:
            raise BlockedRequestError(f"DNS resolution failed for {host!r}")
        return [ipaddress.ip_address(a) for a in mapping[host]]

    return resolve


# --- literal IPs / ranges the task requires us to block ----------------------

@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://127.42.0.9/",              # 127.0.0.0/8
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata / link-local
        "http://10.0.0.5/",               # 10.0.0.0/8
        "http://172.16.10.10/",           # 172.16.0.0/12
        "http://172.31.255.255/",         # 172.16.0.0/12 upper edge
        "http://192.168.1.1/",            # 192.168.0.0/16
        "http://[::1]/",                  # IPv6 loopback
        "http://[fd00::1]/",              # IPv6 ULA (private)
        "http://[fe80::1]/",              # IPv6 link-local
        "http://[::ffff:127.0.0.1]/",     # IPv4-mapped loopback
        "http://0.0.0.0/",                # unspecified
    ],
)
def test_blocks_internal_ip_literals(url, monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve", _fake_resolver({"localhost": ["127.0.0.1"]}))
    with pytest.raises(BlockedRequestError):
        assert_public_url(url)


def test_blocks_non_http_schemes():
    for url in ("file:///etc/passwd", "gopher://x/", "ftp://x/", "data:text/plain,hi"):
        with pytest.raises(BlockedRequestError):
            assert_public_url(url)


def test_blocks_hostname_that_resolves_to_private(monkeypatch):
    monkeypatch.setattr(
        ssrf, "_resolve", _fake_resolver({"sneaky.example.com": ["93.184.216.34", "10.1.2.3"]})
    )
    # one public + one private record => still blocked (we require ALL public)
    with pytest.raises(BlockedRequestError):
        assert_public_url("https://sneaky.example.com/")


# --- allowed destinations ---------------------------------------------------

def test_allows_public_ip_literal():
    ips = assert_public_url("https://8.8.8.8/")
    assert ipaddress.ip_address("8.8.8.8") in ips


def test_allows_external_https_hostname(monkeypatch):
    monkeypatch.setattr(
        ssrf, "_resolve", _fake_resolver({"api.openai.com": ["104.18.0.1", "104.18.1.1"]})
    )
    ips = assert_public_url("https://api.openai.com/v1/models")
    assert all(ip.is_global for ip in ips)


# --- redirect handling ----------------------------------------------------

async def test_redirect_to_private_ip_is_blocked(monkeypatch):
    monkeypatch.setattr(
        ssrf, "_resolve", _fake_resolver({"evil.example.com": ["93.184.216.34"]})
    )

    def handler(request: httpx.Request) -> httpx.Response:
        # first hop 302s to an internal host
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/"})

    with pytest.raises(BlockedRequestError):
        await guarded_get(
            "https://evil.example.com/start", transport=httpx.MockTransport(handler)
        )


async def test_redirect_to_public_is_followed(monkeypatch):
    monkeypatch.setattr(
        ssrf,
        "_resolve",
        _fake_resolver(
            {"a.example.com": ["93.184.216.34"], "b.example.com": ["93.184.216.35"]}
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "a.example.com":
            return httpx.Response(302, headers={"location": "https://b.example.com/final"})
        return httpx.Response(200, text="ok")

    r = await guarded_get(
        "https://a.example.com/start", transport=httpx.MockTransport(handler)
    )
    assert r.status_code == 200


async def test_redirect_loop_is_capped(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve", _fake_resolver({"loop.example.com": ["93.184.216.34"]}))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://loop.example.com/again"})

    with pytest.raises(BlockedRequestError):
        await guarded_get(
            "https://loop.example.com/", transport=httpx.MockTransport(handler)
        )


# --- end-to-end through the credential-test service -------------------------

async def test_credential_test_generic_url_blocks_ssrf(monkeypatch):
    from app.models import CredentialType
    from app.services.credential_test import run_test

    res = await run_test(
        provider="custom",
        ctype=CredentialType.bearer,
        secret={"token": "t"},
        meta={"test_url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert res.ok is False
    assert "blocked" in res.detail.lower()
