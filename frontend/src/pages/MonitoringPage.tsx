import { useMemo } from "react";
import { useMonitorWebSocket } from "@/hooks/useMonitorWebSocket";
import { useSystemStatus } from "@/hooks/queries";
import { Badge, Card, CardTitle, PageHeader, Sparkline } from "@/components/ui";
import { ServiceRow, StatCard } from "@/components/common";
import { formatUptime, pct, relativeTime } from "@/utils/format";
import type { SocketStatus } from "@/websocket/socket";

const liveBadge: Record<SocketStatus, { tone: "success" | "warning" | "neutral"; label: string }> = {
  open: { tone: "success", label: "LIVE" },
  connecting: { tone: "warning", label: "CONNECTING" },
  reconnecting: { tone: "warning", label: "RECONNECTING" },
  closed: { tone: "neutral", label: "OFFLINE" },
};

export function MonitoringPage() {
  const monitor = useMonitorWebSocket();
  const fallbackStatus = useSystemStatus(!monitor.live && monitor.services.length === 0);

  const badge = liveBadge[monitor.status];

  const cpu = useMemo(() => monitor.history.map((p) => p.cpu), [monitor.history]);
  const mem = useMemo(() => monitor.history.map((p) => p.memory), [monitor.history]);
  const disk = useMemo(() => monitor.history.map((p) => p.disk), [monitor.history]);

  const services =
    monitor.services.length > 0
      ? monitor.services
      : (fallbackStatus.data?.services ?? []).map((s) => ({
          name: s.name,
          status: s.status,
          online: s.online,
          latency_ms: s.latency_ms,
          detail: s.detail,
          updatedAt: fallbackStatus.data?.checked_at ?? "",
        }));

  const m = monitor.latest;

  return (
    <div>
      <PageHeader
        title="Monitoring"
        description="Real-time resource and service metrics streamed over WebSocket."
        actions={
          <div className="flex items-center gap-2">
            <Badge tone={badge.tone}>
              <span
                className={
                  "mr-1 inline-block h-2 w-2 rounded-full " +
                  (monitor.live ? "animate-pulse bg-ok" : "bg-warn")
                }
              />
              {badge.label}
            </Badge>
            {monitor.lastEventAt && (
              <span className="text-xs text-muted">updated {relativeTime(monitor.lastEventAt)}</span>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="CPU" value={pct(m?.cpu_percent)} accent={(m?.cpu_percent ?? 0) > 85 ? "danger" : "ok"} />
        <StatCard label="Memory" value={pct(m?.memory_percent)} accent={(m?.memory_percent ?? 0) > 90 ? "danger" : "ok"} />
        <StatCard label="Disk" value={pct(m?.disk_percent)} accent={(m?.disk_percent ?? 0) > 90 ? "danger" : "ok"} />
        <StatCard
          label="Load / Uptime"
          value={m?.load_avg_1m != null ? m.load_avg_1m.toFixed(2) : "—"}
          sub={m ? formatUptime(m.uptime_seconds) : undefined}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card>
          <Sparkline values={cpu} label="CPU" unit="%" />
        </Card>
        <Card>
          <Sparkline values={mem} label="Memory" unit="%" />
        </Card>
        <Card>
          <Sparkline values={disk} label="Disk" unit="%" />
        </Card>
      </div>

      <Card className="mt-4">
        <CardTitle>Services</CardTitle>
        {services.length === 0 ? (
          <p className="text-sm text-muted">Waiting for the first monitoring frame…</p>
        ) : (
          <div>
            {services.map((s) => (
              <ServiceRow
                key={s.name}
                name={s.name}
                status={s.status}
                online={s.online}
                latency={s.latency_ms}
                detail={s.detail}
              />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
