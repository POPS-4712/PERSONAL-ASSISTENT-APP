import { useEffect, useRef, useState } from "react";
import { WS_URL } from "@/config";
import { getAccessToken } from "@/api/tokenStore";
import { refreshAccessToken } from "@/api/client";
import { createReconnectingSocket, type SocketStatus } from "@/websocket/socket";
import type { LogEntry } from "@/api/types";

const BUFFER_LIMIT = 1000;

let counter = 0;

export interface StreamLog extends LogEntry {
  _id: number;
}

export interface LogsStreamState {
  status: SocketStatus;
  live: boolean;
  logs: StreamLog[];
  clear: () => void;
}

/**
 * Subscribes to `WS /ws/logs`. `level` is the server-side minimum level; changing
 * it re-opens the socket with the new filter. Source/text filtering is done by
 * the caller on the returned buffer.
 */
export function useLogsWebSocket(level: string): LogsStreamState {
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const [logs, setLogs] = useState<StreamLog[]>([]);
  const refreshing = useRef(false);

  useEffect(() => {
    setLogs([]);
    const socket = createReconnectingSocket({
      url: () => {
        const token = getAccessToken();
        return token
          ? `${WS_URL}/ws/logs?token=${encodeURIComponent(token)}&level=${encodeURIComponent(level)}`
          : null;
      },
      onStatus: setStatus,
      onMessage: (raw) => {
        const evt = raw as Record<string, unknown>;
        if (evt.type !== "log") return;
        setLogs((prev) =>
          [...prev, { ...(evt as unknown as LogEntry), _id: ++counter }].slice(-BUFFER_LIMIT),
        );
      },
      shouldRetry: (event) => {
        if (event.code === 1008 && !refreshing.current) {
          refreshing.current = true;
          void refreshAccessToken().finally(() => {
            refreshing.current = false;
          });
        }
        return true;
      },
    });
    return () => socket.close();
  }, [level]);

  return {
    status,
    live: status === "open",
    logs,
    clear: () => setLogs([]),
  };
}
