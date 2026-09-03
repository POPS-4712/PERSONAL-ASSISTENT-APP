"""Unit tests for N8nService error handling.

httpx.MockTransport is a real transport driving the real client code — this
exercises our request/response/error mapping, it does not fake the feature.
The live-integration test lives in test_n8n_integration.py and is opt-in.
"""
from __future__ import annotations

import httpx
import pytest

from app.services.n8n import (
    N8nAuthError,
    N8nNotConfigured,
    N8nNotFound,
    N8nService,
    N8nUnavailable,
    N8nUnsupported,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _svc(handler, api_key="k") -> N8nService:
    return N8nService(
        base_url="http://n8n:5678", api_key=api_key, transport=httpx.MockTransport(handler)
    )


WF = {"id": "wf1", "name": "Asistente - Noticias", "active": False, "nodes": []}


async def test_list_workflows_unwraps_data():
    def h(req: httpx.Request) -> httpx.Response:
        assert req.headers["x-n8n-api-key"] == "k"
        return httpx.Response(200, json={"data": [WF], "nextCursor": None})

    assert (await _svc(h).list_workflows())[0]["name"] == "Asistente - Noticias"


async def test_missing_api_key_raises_not_configured():
    with pytest.raises(N8nNotConfigured):
        await N8nService(api_key="").list_workflows()


async def test_401_maps_to_auth_error():
    with pytest.raises(N8nAuthError):
        await _svc(lambda r: httpx.Response(401, json={"message": "unauthorized"})).list_workflows()


async def test_404_maps_to_not_found():
    with pytest.raises(N8nNotFound):
        await _svc(lambda r: httpx.Response(404)).get_workflow("nope")


async def test_500_maps_to_bad_gateway():
    with pytest.raises(Exception) as ei:
        await _svc(lambda r: httpx.Response(503)).list_workflows()
    assert ei.value.status_code == 502


async def test_connection_error_maps_to_unavailable():
    def boom(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(N8nUnavailable):
        await _svc(boom).list_workflows()


async def test_timeout_maps_to_unavailable():
    def slow(req):
        raise httpx.ReadTimeout("too slow")

    with pytest.raises(N8nUnavailable):
        await _svc(slow).list_workflows()


async def test_run_workflow_is_unsupported_but_names_webhook():
    wf = {**WF, "nodes": [{"type": "n8n-nodes-base.webhook", "parameters": {"path": "abc"}}]}
    with pytest.raises(N8nUnsupported) as ei:
        await _svc(lambda r: httpx.Response(200, json=wf)).run_workflow("wf1")
    assert "/webhook/abc" in ei.value.message


async def test_activate_deactivate_roundtrip():
    seen = []

    def h(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.path)
        return httpx.Response(200, json={**WF, "active": req.url.path.endswith("/activate")})

    svc = _svc(h)
    assert (await svc.activate("wf1"))["active"] is True
    assert (await svc.deactivate("wf1"))["active"] is False
    assert seen == ["/api/v1/workflows/wf1/activate", "/api/v1/workflows/wf1/deactivate"]


async def test_health_reports_unreachable_without_raising():
    def boom(req):
        raise httpx.ConnectError("refused")

    out = await _svc(boom, api_key="k").health()
    assert out["reachable"] is False and out["api_key_configured"] is True


async def test_health_without_api_key_is_not_configured_and_does_not_probe():
    calls = []

    def spy(req):
        calls.append(req.url.path)
        return httpx.Response(200, json={"status": "ok"})

    out = await _svc(spy, api_key="").health()
    assert out["status"] == "not_configured"
    assert out["api_key_configured"] is False
    assert out["reachable"] is False
    # an unconfigured integration must not be probed: a Compose hostname that
    # does not resolve would otherwise be reported as an outage
    assert calls == []


async def test_health_ok_and_key_valid():
    def h(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(200, json={"data": []})

    out = await _svc(h).health()
    assert out["reachable"] is True and out["api_key_valid"] is True
