/**
 * A single reconnecting WebSocket. Exponential backoff with jitter, clean
 * teardown, and a status callback. Callers get one socket per hook instance;
 * nothing here opens more than one connection at a time.
 */
export type SocketStatus = "connecting" | "open" | "reconnecting" | "closed";

export interface ReconnectingSocketOptions {
  url: () => string | null;
  onMessage: (data: unknown) => void;
  onStatus?: (status: SocketStatus) => void;
  /** Return true to keep retrying after a close, false to give up. */
  shouldRetry?: (event: CloseEvent, attempt: number) => boolean;
  maxDelayMs?: number;
  baseDelayMs?: number;
}

export interface ReconnectingSocket {
  close: () => void;
  reconnect: () => void;
  status: () => SocketStatus;
}

export function createReconnectingSocket(opts: ReconnectingSocketOptions): ReconnectingSocket {
  const baseDelay = opts.baseDelayMs ?? 1000;
  const maxDelay = opts.maxDelayMs ?? 30000;

  let ws: WebSocket | null = null;
  let attempt = 0;
  let disposed = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let status: SocketStatus = "connecting";

  const setStatus = (s: SocketStatus) => {
    status = s;
    opts.onStatus?.(s);
  };

  const clearTimer = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  };

  const scheduleReconnect = () => {
    if (disposed) return;
    const delay = Math.min(maxDelay, baseDelay * 2 ** attempt) * (0.7 + Math.random() * 0.6);
    attempt += 1;
    setStatus("reconnecting");
    clearTimer();
    timer = setTimeout(connect, delay);
  };

  function connect() {
    if (disposed) return;
    const url = opts.url();
    if (!url) {
      // no token yet — wait and retry
      scheduleReconnect();
      return;
    }
    setStatus(attempt === 0 ? "connecting" : "reconnecting");
    try {
      ws = new WebSocket(url);
    } catch {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      attempt = 0;
      setStatus("open");
    };

    ws.onmessage = (ev) => {
      try {
        opts.onMessage(JSON.parse(ev.data));
      } catch {
        /* ignore non-JSON frames */
      }
    };

    ws.onclose = (ev) => {
      ws = null;
      if (disposed) {
        setStatus("closed");
        return;
      }
      const retry = opts.shouldRetry ? opts.shouldRetry(ev, attempt) : true;
      if (retry) scheduleReconnect();
      else setStatus("closed");
    };

    ws.onerror = () => {
      // onclose will follow and drive reconnection
      ws?.close();
    };
  }

  connect();

  return {
    close() {
      disposed = true;
      clearTimer();
      if (ws) {
        ws.onclose = null;
        ws.onerror = null;
        ws.close();
        ws = null;
      }
      setStatus("closed");
    },
    reconnect() {
      attempt = 0;
      clearTimer();
      if (ws) {
        ws.onclose = null;
        ws.close();
        ws = null;
      }
      connect();
    },
    status: () => status,
  };
}
