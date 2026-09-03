import { Link } from "react-router-dom";
import { ApiError } from "@/api";
import { n8nStateOf, useN8nHealth, useWorkflowMutations, useWorkflows } from "@/hooks/queries";
import { useToast } from "@/stores/toast";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  PageHeader,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { QueryBoundary, errorMessage } from "@/components/common";
import { relativeTime } from "@/utils/format";

export function AutomationsPage() {
  const n8n = useN8nHealth();
  const workflows = useWorkflows();
  const m = useWorkflowMutations();
  const toast = useToast();

  const n8nState = n8nStateOf(n8n.data, n8n.isError);

  function toggle(id: string, active: boolean) {
    const p = active ? m.deactivate.mutateAsync(id) : m.activate.mutateAsync(id);
    p.then(() => toast.success(active ? "Workflow deactivated" : "Workflow activated")).catch((e) =>
      toast.error("Failed", errorMessage(e)),
    );
  }

  async function run(id: string) {
    try {
      await m.run.mutateAsync(id);
      toast.success("Workflow triggered");
    } catch (e) {
      if (e instanceof ApiError && e.status === 501) {
        toast.info("Run unavailable", "This n8n version does not expose workflow execution through the API.");
      } else {
        toast.error("Run failed", errorMessage(e));
      }
    }
  }

  return (
    <div>
      <PageHeader
        title="Automations"
        description="n8n workflows managed by Automation Center."
        actions={
          n8n.data && (
            <Badge
              tone={
                n8nState === "offline"
                  ? "danger"
                  : n8nState === "not_configured" || n8n.data.api_key_valid === false
                    ? "warning"
                    : "success"
              }
            >
              n8n{" "}
              {n8nState === "offline"
                ? "offline"
                : n8nState === "not_configured"
                  ? "not configured"
                  : n8n.data.api_key_valid === false
                    ? "invalid API key"
                    : "connected"}
            </Badge>
          )
        }
      />

      {n8nState === "not_configured" ? (
        <Card className="border-warn/40">
          <p className="text-sm text-warn">
            No n8n instance is configured on the backend. Set <code>AC_N8N_BASE_URL</code> and{" "}
            <code>AC_N8N_API_KEY</code> to manage workflows from here.
          </p>
        </Card>
      ) : n8nState === "offline" ? (
        <EmptyState
          title="n8n is offline"
          description="Automation workflows are temporarily unavailable. Check that the n8n service is running."
        />
      ) : (
        <QueryBoundary
          isLoading={workflows.isLoading}
          isError={workflows.isError}
          error={workflows.error}
          onRetry={() => workflows.refetch()}
          skeletonRows={4}
        >
          {workflows.data && workflows.data.data.length === 0 ? (
            <EmptyState title="No workflows" description="Create a workflow in n8n to manage it here." />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Workflow</TH>
                  <TH>Status</TH>
                  <TH>Updated</TH>
                  <TH className="text-right">Actions</TH>
                </TR>
              </THead>
              <TBody>
                {workflows.data?.data.map((w) => (
                  <TR key={w.id}>
                    <TD>
                      <Link to={`/automations/${w.id}`} className="font-medium text-fg hover:text-brand">
                        {w.name}
                      </Link>
                      <span className="ml-2 font-mono text-[11px] text-muted">{w.id}</span>
                    </TD>
                    <TD>
                      <Badge tone={w.active ? "success" : "neutral"}>{w.active ? "active" : "inactive"}</Badge>
                    </TD>
                    <TD className="text-muted">{relativeTime(w.updatedAt)}</TD>
                    <TD>
                      <div className="flex justify-end gap-1.5">
                        <Button size="sm" variant="outline" onClick={() => toggle(w.id, w.active)}>
                          {w.active ? "Deactivate" : "Activate"}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          title="n8n's public API cannot execute workflows on demand"
                          onClick={() => run(w.id)}
                        >
                          Run
                        </Button>
                        <Link to={`/executions?workflow_id=${w.id}`}>
                          <Button size="sm" variant="ghost">
                            Executions
                          </Button>
                        </Link>
                      </div>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
          <p className="mt-3 text-xs text-muted">
            “Run” asks the backend to trigger a workflow. n8n's public API has no execute endpoint, so for
            most workflows this returns guidance on how to trigger it (webhook or the n8n editor) rather
            than a fake execution.
          </p>
        </QueryBoundary>
      )}
    </div>
  );
}
