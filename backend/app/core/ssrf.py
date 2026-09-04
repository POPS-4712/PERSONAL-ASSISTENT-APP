"""SSRF guard for outbound HTTP triggered by user-controlled input.

The credential-test feature lets a user store an arbitrary ``meta.test_url`` and
have the backend GET it with the decrypted secret attached. Without a guard that
is a server-side request forgery primitive: an attacker could point it at
``http://169.254.169.254/`` (cloud metadata), ``http://localhost:5678`` (the
internal n8n), or any RFC1918 host and read the response / port-scan.

``guarded_get`` enforces, on every hop (including redirects):

* scheme is ``http`` or ``https`` only;
* the host resolves (DNS) and **every** resulting A/AAAA record is a public,
  globally-routable address — loopback, link-local (incl. 169.254.169.254),
  RFC1918, carrier-grade NAT, ULA (fc00::/7), IPv6 loopback ``::1`` and
  IPv4-mapped IPv6 are all rejected;
* redirects are not followed automatically; each ``Location`` is re-validated
  before the next request, so a public URL cannot bounce us to an internal one;
* a short timeout.

Residual risk: httpx re-resolves the hostname when it opens the socket, so a
DNS-rebinding server that flips the record between our check and that connect
could still slip through a private IP. The window is milliseconds and we
re-validate immediately before each send; closing it fully needs socket-level
IP pinning, tracked as a follow-up. For a connection *test* (no secret is
returned to the caller, only ok/latency) this is an acceptable RC posture.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

import httpx

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_REDIRECTS = 3
_DEFAULT_TIMEOUT = 6.0

# Explicit belt-and-braces list; each entry is also covered by the range checks.
_ALWAYS_BLOCK = {"169.254.169.254", "fd00:ec2::254"}

IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class BlockedRequestError(Exception):
    """The requested URL points at a destination we refuse to contact."""


def _normalise(ip: IpAddress) -> IpAddress:
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped
        if mapped is not None:
            return mapped
    return ip


def _is_blocked(ip: IpAddress) -> bool:
    ip = _normalise(ip)
    if str(ip) in _ALWAYS_BLOCK:
        return True
    return (
        not ip.is_global
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve(host: str) -> list[IpAddress]:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:  # noqa: PERF203
        raise BlockedRequestError(f"DNS resolution failed for {host!r}") from exc
    addrs: list[IpAddress] = []
    for info in infos:
        raw = info[4][0].split("%", 1)[0]  # strip any zone id
        try:
            addrs.append(ipaddress.ip_address(raw))
        except ValueError:
            continue
    return addrs


def assert_public_url(url: str) -> list[IpAddress]:
    """Raise ``BlockedRequestError`` unless ``url`` is safe to fetch.

    Returns the list of resolved public IPs (useful for callers / tests).
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise BlockedRequestError(f"scheme {parts.scheme!r} is not allowed (http/https only)")
    host = parts.hostname
    if not host:
        raise BlockedRequestError("URL has no host")

    try:
        literal = ipaddress.ip_address(host)
        ips: list[IpAddress] = [literal]
    except ValueError:
        ips = _resolve(host)

    if not ips:
        raise BlockedRequestError(f"no usable address for {host!r}")
    for ip in ips:
        if _is_blocked(ip):
            raise BlockedRequestError(f"destination {ip} is not a public address")
    return ips


def assert_not_metadata_url(url: str) -> None:
    """Weaker guard for *operator-configured* service endpoints.

    ``assert_public_url`` is the right rule for a URL a user typed into a
    credential: it must be publicly routable. It is the wrong rule here,
    because the legitimate value for a service endpoint is usually private -
    ``http://playwright:3000`` on a Docker network, or a Render private
    service. Blocking those would break the product.

    What has no legitimate use as a service endpoint is a cloud metadata
    address, so that is what this refuses: an admin (or anyone who has taken
    an admin account) must not be able to aim the health prober at
    ``169.254.169.254`` and use response codes and timings as an oracle.

    Note this is a narrower guarantee than ``assert_public_url``. Configuring
    a service endpoint is an admin-only, audited action, and the probe returns
    only a status code and a latency - never a response body.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise BlockedRequestError(f"scheme {parts.scheme!r} is not allowed (http/https only)")
    host = parts.hostname
    if not host:
        raise BlockedRequestError("URL has no host")

    if host in _ALWAYS_BLOCK:
        raise BlockedRequestError(f"{host} is a cloud metadata endpoint")
    try:
        ip = _normalise(ipaddress.ip_address(host))
    except ValueError:
        return  # a hostname: resolution happens at probe time, see the note above
    if str(ip) in _ALWAYS_BLOCK or ip.is_link_local:
        raise BlockedRequestError(f"{ip} is a link-local / metadata address")


async def guarded_get(
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.Response:
    """GET ``url`` with SSRF protection and manual, re-validated redirects.

    ``transport`` is an injection point for tests only.
    """
    current = url
    query = params or {}
    redirects = 0
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout), follow_redirects=False, transport=transport
    ) as client:
        while True:
            assert_public_url(current)
            response = await client.get(current, headers=headers or {}, params=query)
            location = response.headers.get("location")
            if response.is_redirect and location:
                redirects += 1
                if redirects > _MAX_REDIRECTS:
                    raise BlockedRequestError("too many redirects")
                current = str(response.url.join(location))
                query = {}  # redirect target already carries its own query
                continue
            return response
