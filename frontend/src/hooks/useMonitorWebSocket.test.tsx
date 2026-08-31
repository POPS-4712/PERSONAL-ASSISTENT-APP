import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useMonitorWebSocket } from "./useMonitorWebSocket";
import { useLogsWebSocket } from "./useLogsWebSocket";
import { setSession } from "@/api/tokenStore";
import { sampleUser } from "@/test/utils";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }
  close() {
    this.onclose?.({ code: 1000 });
  }
  open() {
    this.onopen?.();
  }
  message(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  setSession({ access_token: "tok", refresh_token: "r", expires_at: Date.now() + 60_000, user: sampleUser });
});

afterEach(() => {
  vi.unstubAllGlobals();
  setSession(null);
});

describe("useMonitorWebSocket", () => {
  it("puts the access token in the socket URL", () => {
    renderHook(() => useMonitorWebSocket());
    expect(MockWebSocket.instances[0].url).toContain("/ws/monitor?token=tok");
  });

  it("accumulates metrics history and service status from real events", async () => {
    const { result } = renderHook(() => useMonitorWebSocket());
    const ws = MockWebSocket.instances[0];

    act(() => ws.open());
    act(() =>
      ws.message({
        type: "system.metrics",
        timestamp: new Date().toISOString(),
        cpu: 30,
        memory: 50,
        disk: 40,
        detail: { cpu_percent: 30, memory_percent: 50, disk_percent: 40 },
      }),
    );
    act(() =>
      ws.message({
        type: "service.status",
        timestamp: new Date().toISOString(),
        service: "n8n",
        status: "online",
        latency_ms: 5,
        detail: "HTTP 200",
      }),
    );

    await waitFor(() => expect(result.current.live).toBe(true));
    expect(result.current.history).toHaveLength(1);
    expect(result.current.latest?.cpu_percent).toBe(30);
    expect(result.current.services[0]).toMatchObject({ name: "n8n", online: true });
  });
});

describe("useLogsWebSocket", () => {
  it("subscribes with the level filter and buffers log frames", async () => {
    const { result } = renderHook(() => useLogsWebSocket("WARNING"));
    const ws = MockWebSocket.instances[0];
    expect(ws.url).toContain("level=WARNING");

    act(() => ws.open());
    act(() => ws.message({ type: "log", timestamp: new Date().toISOString(), level: "WARNING", source: "backend", message: "disk low", correlation_id: null }));
    act(() => ws.message({ type: "hello" }));

    await waitFor(() => expect(result.current.logs).toHaveLength(1));
    expect(result.current.logs[0].message).toBe("disk low");
  });
});
