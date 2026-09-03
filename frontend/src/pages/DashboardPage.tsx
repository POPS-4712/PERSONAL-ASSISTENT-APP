import { Link } from "react-router-dom";
import {
  useHealth,
  useN8nHealth,
  useSystemMetrics,
  useSystemStatus,
  useWorkflows,
} from "@/hooks/queries";
import { Badge, Card, CardTitle, EmptyState } from "@/components/ui";
import { PageHeader } from "@/components/ui";
import { QueryBoundary, ServiceRow, StatCard, errorMessage } from "@/components/common";
import { bytesFromMb, formatUptime, pct, relativeTime } from "@/utils/format";

export function DashboardPage() {
  const health = useHealth();
  const status = useSystemStatus();
  const metrics = useSystemMetrics();
  const n8n = useN8nHealth();
  const workflows = useWorkflows();

  const operational = status.data?.operational;
  const overall = health.isError
    ? { tone: "danger" as const, label: "Backend offline" }
    : operational
      ? { tone: "success" as const, label: "Operational" }
      : status.data
        ? { tone: "warning" as const, label: "Degraded" }
        : { tone: "neutral" as const, label: "Checking…" };

  const m = metrics.data;
  const activeWorkflows = workflows.data?.data.filter((w) => w.active).length ?? 0;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Live status of the Automation Center stack."
        actions={<Badge tone={overall.tone}>● {overall.label}</Badge>}
      />

      {health.isError && (
        <div className="mb-6 rounded-xl border border-danger/30 bg-danger/5 p-4 text-sm">
          <p className="font-semibold text-danger">Unable to connect to the Automation Center backend.</p>
          <p className="mt-1 text-muted">{errorMessage(health.error)}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="CPU"
          value={metrics.isLoading ? "…" : pct(m?.cpu_percent)}
          accent={(m?.cpu_percent ?? 0) > 85 ? "danger" : (m?.cpu_percent ?? 0) > 65 ? "warn" : "ok"}
        />
        <StatCard
          label="Memory"
          value={metrics.isLoading ? "…" : pct(m?.memory_percent)}
          sub={m ? `${bytesFromMb(m.memory_used_mb)} / ${bytesFromMb(m.memory_total_mb)}` : undefined}
          accent={(m?.memory_percent ?? 0) > 90 ? "danger" : (m?.memory_percent ?? 0) > 75 ? "warn" : "ok"}
        />
        <StatCard
          label="Disk"
          value={metrics.isLoading ? "…" : pct(m?.disk_percent)}
          sub={m ? `${m.disk_free_gb.toFixed(0)} GB free` : undefined}
          accent={(m?.disk_percent ?? 0) > 90 ? "danger" : (m?.disk_percent ?? 0) > 75 ? "warn" : "ok"}
        />
        <StatCard
          label="Uptime"
          value={m ? formatUptime(m.uptime_seconds) : "…"}
          sub={m ? `sampled ${relativeTime(m.sampled_at)}` : undefined}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle action={<Link to="/monitoring" className="text-xs text-brand hover:underline">Monitor</Link>}>
            Services
          </CardTitle>
          <QueryBoundary
            isLoading={status.isLoading}
            isError={status.isError}
            error={status.error}
            onRetry={() => status.refetch()}
            skeletonRows={5}
          >
            {status.data && (
              <div>
                {status.data.services.map((s) => (
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
          </QueryBoundary>
        </Card>

        <Card>
          <CardTitle action={<Link to="/automations" className="text-xs text-brand hover:underline">All</Link>}>
            Automations (n8n)
          </CardTitle>
          {n8n.data && !n8n.data.reachable ? (
            <EmptyState
              title="n8n is offline"
              description="Automation workflows are temporarily unavailable."
            />
          ) : (
            <QueryBoundary
              isLoading={workflows.isLoading}
              isError={workflows.isError}
              error={workflows.error}
              onRetry={() => workflows.refetch()}
            >
              {workflows.data && workflows.data.data.length === 0 ? (
                <EmptyState title="No workflows found" description="Create workflows in n8n to see them here." />
              ) : (
                <div className="space-y-2">
                  <div className="flex gap-6 text-sm">
                    <div>
                      <p className="text-2xl font-semibold text-fg">{workflows.data?.data.length ?? 0}</p>
                      <p className="text-xs text-muted">total</p>
                    </div>
                    <div>
                      <p className="text-2xl font-semibold text-ok">{activeWorkflows}</p>
                      <p className="text-xs text-muted">active</p>
                    </div>
                  </div>
                  <ul className="mt-2 divide-y divide-border">
                    {workflows.data?.data.slice(0, 6).map((w) => (
                      <li key={w.id} className="flex items-center justify-between py-2 text-sm">
                        <Link to={`/automations/${w.id}`} className="truncate text-fg hover:text-brand">
                          {w.name}
                        </Link>
                        <Badge tone={w.active ? "success" : "neutral"}>{w.active ? "active" : "inactive"}</Badge>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </QueryBoundary>
          )}
        </Card>
      </div>

      {health.data?.problems && health.data.problems.length > 0 && (
        <Card className="mt-6 border-warn/40">
          <CardTitle>Configuration warnings</CardTitle>
          <ul className="list-inside list-disc space-y-1 text-sm text-warn">
            {health.data.problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
