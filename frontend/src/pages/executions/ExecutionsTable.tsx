import type { UseQueryResult } from "@tanstack/react-query";
import { Badge, EmptyState, Table, TBody, TD, TH, THead, TR } from "@/components/ui";
import { QueryBoundary } from "@/components/common";
import { formatDateTime, formatDuration } from "@/utils/format";
import type { N8nExecution } from "@/api/types";

type Tone = "success" | "danger" | "warning" | "neutral" | "info";

export function executionStatus(e: N8nExecution): { label: string; tone: Tone } {
  const raw = (e.status ?? (e.finished ? "success" : "running")).toString().toLowerCase();
  switch (raw) {
    case "success":
      return { label: "SUCCESS", tone: "success" };
    case "error":
    case "failed":
    case "crashed":
      return { label: "FAILED", tone: "danger" };
    case "running":
    case "new":
      return { label: "RUNNING", tone: "info" };
    case "waiting":
      return { label: "WAITING", tone: "warning" };
    case "canceled":
    case "cancelled":
      return { label: "CANCELLED", tone: "neutral" };
    default:
      return { label: raw.toUpperCase(), tone: "neutral" };
  }
}

function durationSeconds(e: N8nExecution): number | null {
  if (!e.startedAt || !e.stoppedAt) return null;
  const d = (new Date(e.stoppedAt).getTime() - new Date(e.startedAt).getTime()) / 1000;
  return Number.isFinite(d) && d >= 0 ? d : null;
}

export function ExecutionsTable({
  query,
  compact = false,
  showWorkflow = true,
}: {
  query: UseQueryResult<{ data: N8nExecution[] }>;
  compact?: boolean;
  showWorkflow?: boolean;
}) {
  return (
    <QueryBoundary
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
      skeletonRows={compact ? 3 : 6}
    >
      {query.data && query.data.data.length === 0 ? (
        <EmptyState title="No executions" description="Executions appear here once workflows have run." />
      ) : (
        <Table>
          <THead>
            <TR>
              {showWorkflow && <TH>Workflow</TH>}
              <TH>Status</TH>
              <TH>Started</TH>
              {!compact && <TH>Finished</TH>}
              <TH>Duration</TH>
            </TR>
          </THead>
          <TBody>
            {query.data?.data.map((e) => {
              const s = executionStatus(e);
              return (
                <TR key={e.id}>
                  {showWorkflow && (
                    <TD className="font-mono text-xs text-muted">{e.workflowId ?? "—"}</TD>
                  )}
                  <TD>
                    <Badge tone={s.tone}>{s.label}</Badge>
                  </TD>
                  <TD className="text-muted">{formatDateTime(e.startedAt)}</TD>
                  {!compact && <TD className="text-muted">{formatDateTime(e.stoppedAt)}</TD>}
                  <TD className="tabular-nums">{formatDuration(durationSeconds(e))}</TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      )}
    </QueryBoundary>
  );
}
