import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createReconnectingSocket } from "./socket";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 0;
  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }
  close() {
    this.readyState = 3;
    this.onclose?.({ code: 1000 });
  }
  emitOpen() {
    this.readyState = 1;
    this.onopen?.();
  }
  emitMessage(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
  emitClose(code = 1006) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("createReconnectingSocket", () => {
  it("delivers parsed messages and reports open status", () => {
    const onMessage = vi.fn();
    const onStatus = vi.fn();
    createReconnectingSocket({ url: () => "ws://x/ws", onMessage, onStatus });

    MockWebSocket.instances[0].emitOpen();
    MockWebSocket.instances[0].emitMessage({ type: "log", message: "hi" });

    expect(onStatus).toHaveBeenCalledWith("open");
    expect(onMessage).toHaveBeenCalledWith({ type: "log", message: "hi" });
  });

  it("reconnects with backoff after an unexpected close", () => {
    const onStatus = vi.fn();
    createReconnectingSocket({ url: () => "ws://x/ws", onMessage: vi.fn(), onStatus, baseDelayMs: 100 });

    MockWebSocket.instances[0].emitOpen();
    MockWebSocket.instances[0].emitClose(1006);
    expect(onStatus).toHaveBeenCalledWith("reconnecting");

    vi.advanceTimersByTime(500);
    expect(MockWebSocket.instances.length).toBe(2);
  });

  it("stops retrying when shouldRetry returns false", () => {
    createReconnectingSocket({
      url: () => "ws://x/ws",
      onMessage: vi.fn(),
      shouldRetry: () => false,
    });
    MockWebSocket.instances[0].emitClose(1008);
    vi.advanceTimersByTime(5000);
    expect(MockWebSocket.instances.length).toBe(1);
  });

  it("does not reconnect after close()", () => {
    const socket = createReconnectingSocket({ url: () => "ws://x/ws", onMessage: vi.fn() });
    MockWebSocket.instances[0].emitOpen();
    socket.close();
    vi.advanceTimersByTime(10_000);
    expect(MockWebSocket.instances.length).toBe(1);
  });
});
