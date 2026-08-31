import { useAuth } from "@/stores/auth";
import { useHealth, useLogsBacklog, useSystemStatus } from "@/hooks/queries";
import { Badge, Card, CardTitle, EmptyState, PageHeader, Table, TBody, TD, TH, THead, TR } from "@/components/ui";
import { QueryBoundary, ServiceRow } from "@/components/common";
import { formatDateTime } from "@/utils/format";

export function AdminUsersPage() {
  const { user } = useAuth();
  return (
    <div>
      <PageHeader title="Users" description="User administration." />
      <Card>
        <CardTitle>Current admin</CardTitle>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted">Username</dt>
            <dd className="text-fg">{user?.username}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Email</dt>
            <dd className="text-fg">{user?.email}</dd>
          </div>
        </dl>
      </Card>
      <div className="mt-4">
        <EmptyState
          title="User management API not yet exposed"
          description="The backend does not expose a user-list endpoint in this release. New users are created through the installer or the open-registration flow."
        />
      </div>
    </div>
  );
}

export function AdminSystemPage() {
  const health = useHealth();
  const status = useSystemStatus();
  return (
    <div>
      <PageHeader title="System" description="Backend health and service topology." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle>Backend</CardTitle>
          <QueryBoundary isLoading={health.isLoading} isError={health.isError} error={health.error} onRetry={() => health.refetch()}>
            {health.data && (
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted">Status</dt>
                  <dd>
                    <Badge tone={health.data.status === "ok" ? "success" : "warning"}>{health.data.status}</Badge>
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">Version</dt>
                  <dd className="text-fg">{health.data.version}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">Environment</dt>
                  <dd className="text-fg">{health.data.environment}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">Database</dt>
                  <dd className="text-fg">{health.data.database}</dd>
                </div>
                {health.data.problems.length > 0 && (
                  <div className="mt-2 rounded-lg bg-warn/10 p-2 text-xs text-warn">
                    <ul className="list-inside list-disc">
                      {health.data.problems.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </dl>
            )}
          </QueryBoundary>
        </Card>
        <Card>
          <CardTitle>Services</CardTitle>
          <QueryBoundary isLoading={status.isLoading} isError={status.isError} error={status.error} onRetry={() => status.refetch()}>
            {status.data?.services.map((s) => (
              <ServiceRow key={s.name} name={s.name} online={s.online} latency={s.latency_ms} />
            ))}
          </QueryBoundary>
        </Card>
      </div>
    </div>
  );
}

export function AdminSecurityPage() {
  const logs = useLogsBacklog({ level: "WARNING", limit: 200 });
  return (
    <div>
      <PageHeader title="Security" description="Recent warnings and errors from the backend audit log." />
      <QueryBoundary isLoading={logs.isLoading} isError={logs.isError} error={logs.error} onRetry={() => logs.refetch()} skeletonRows={6}>
        {logs.data && logs.data.data.length === 0 ? (
          <EmptyState title="No recent warnings" description="Nothing above INFO level in the current backlog." />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Time</TH>
                <TH>Level</TH>
                <TH>Source</TH>
                <TH>Message</TH>
              </TR>
            </THead>
            <TBody>
              {logs.data?.data.map((l, i) => (
                <TR key={i}>
                  <TD className="whitespace-nowrap text-muted">{formatDateTime(l.timestamp)}</TD>
                  <TD>
                    <Badge tone={l.level === "ERROR" || l.level === "CRITICAL" ? "danger" : "warning"}>{l.level}</Badge>
                  </TD>
                  <TD className="text-muted">{l.source}</TD>
                  <TD className="text-fg">{l.message}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </QueryBoundary>
    </div>
  );
}
