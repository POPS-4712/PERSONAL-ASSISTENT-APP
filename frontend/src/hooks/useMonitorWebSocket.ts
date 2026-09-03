import { useEffect, useMemo, useRef, useState } from "react";
import { WS_URL } from "@/config";
import { getAccessToken } from "@/api/tokenStore";
import { refreshAccessToken } from "@/api/client";
import { createReconnectingSocket, type SocketStatus } from "@/websocket/socket";
import type { HostMetrics, ServiceState, ServiceStatus } from "@/api/types";

export interface MonitorServiceStatus {
  name: string;
  status: ServiceStatus;
  online: boolean | null;
  latency_ms: number | null;
  detail: string;
  updatedAt: string;
}

export interface MonitorPoint {
  t: string;
  cpu: number;
  memory: number;
  disk: number;
}

interface MetricsEvent {
  type: "system.metrics";
  timestamp: string;
  cpu: number;
  memory: number;
  disk: number;
  detail: HostMetrics;
}

interface ServiceEvent {
  type: "service.status";
  timestamp: string;
  service: string;
  status: ServiceStatus;
  latency_ms: number | null;
  detail: string;
}

const HISTORY_LIMIT = 60;

export interface MonitorState {
  status: SocketStatus;
  live: boolean;
  latest: HostMetrics | null;
  history: MonitorPoint[];
  services: MonitorServiceStatus[];
  lastEventAt: string | null;
}

export function useMonitorWebSocket(): MonitorState {
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const [latest, setLatest] = useState<HostMetrics | null>(null);
  const [history, setHistory] = useState<MonitorPoint[]>([]);
  const [services, setServices] = useState<Record<string, MonitorServiceStatus>>({});
  const [lastEventAt, setLastEventAt] = useState<string | null>(null);
  const refreshing = useRef(false);

  useEffect(() => {
    const socket = createReconnectingSocket({
      url: () => {
        const token = getAccessToken();
        return token ? `${WS_URL}/ws/monitor?token=${encodeURIComponent(token)}` : null;
      },
      onStatus: setStatus,
      onMessage: (raw) => {
        const evt = raw as MetricsEvent | ServiceEvent | { type: string };
        if (evt.type === "system.metrics") {
          const m = evt as MetricsEvent;
          setLatest(m.detail);
          setLastEventAt(m.timestamp);
          setHistory((prev) =>
            [...prev, { t: m.timestamp, cpu: m.cpu, memory: m.memory, disk: m.disk }].slice(-HISTORY_LIMIT),
          );
        } else if (evt.type === "service.status") {
          const s = evt as ServiceEvent;
          setLastEventAt(s.timestamp);
          setServices((prev) => ({
            ...prev,
            [s.service]: {
              name: s.service,
              status: s.status,
              online: s.status === "online" ? true : s.status === "offline" ? false : null,
              latency_ms: s.latency_ms,
              detail: s.detail,
              updatedAt: s.timestamp,
            },
          }));
        }
      },
      shouldRetry: (event) => {
        // 1008 = policy violation → token rejected. Refresh once, then retry.
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
  }, []);

  const serviceList = useMemo(
    () => Object.values(services).sort((a, b) => a.name.localeCompare(b.name)),
    [services],
  );

  return {
    status,
    live: status === "open",
    latest,
    history,
    services: serviceList,
    lastEventAt,
  };
}

export type { ServiceState };
