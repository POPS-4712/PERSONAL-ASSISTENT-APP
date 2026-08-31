import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, authEvents } from "./client";
import { setSession } from "./tokenStore";
import { sampleUser } from "@/test/utils";

function session(access = "old-access") {
  setSession({
    access_token: access,
    refresh_token: "refresh-1",
    expires_at: Date.now() + 60_000,
    user: sampleUser,
  });
}

beforeEach(() => {
  setSession(null);
  vi.unstubAllGlobals();
});

describe("apiRequest", () => {
  it("attaches the bearer token", async () => {
    session("tok-abc");
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.get("/api/thing");

    const call = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const headers = call[1].headers as Record<string, string>;
    expect(headers.authorization).toBe("Bearer tok-abc");
  });

  it("refreshes once on 401 and retries the original request", async () => {
    session("stale");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "expired" }), { status: 401 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ access_token: "fresh", refresh_token: "refresh-2", expires_in: 1800, user: sampleUser }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: 42 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.get<{ data: number }>("/api/thing");

    expect(result.data).toBe(42);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toContain("/api/auth/refresh");
    const retryHeaders = (fetchMock.mock.calls[2][1] as RequestInit).headers as Record<string, string>;
    expect(retryHeaders.authorization).toBe("Bearer fresh");
  });

  it("drops the session and emits 'expired' when refresh fails", async () => {
    session("stale");
    const onExpired = vi.fn();
    authEvents.addEventListener("expired", onExpired);

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "expired" }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "bad refresh" }), { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.get("/api/thing")).rejects.toMatchObject({ status: 401, code: "session_expired" });
    expect(onExpired).toHaveBeenCalled();
    authEvents.removeEventListener("expired", onExpired);
  });

  it("normalises a network failure into ApiError code 'network'", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api.getPublic("/api/health")).rejects.toBeInstanceOf(ApiError);
    await expect(api.getPublic("/api/health")).rejects.toMatchObject({ code: "network" });
  });

  it("extracts n8n typed error detail {code,message}", async () => {
    session();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: { code: "n8n_unsupported", message: "no execute" } }), { status: 501 })),
    );
    await expect(api.post("/api/n8n/workflows/x/run")).rejects.toMatchObject({
      status: 501,
      code: "n8n_unsupported",
      message: "no execute",
    });
  });
});
