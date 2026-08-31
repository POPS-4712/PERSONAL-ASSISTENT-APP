import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/api";
import { useExecutions, useWorkflow, useWorkflowMutations } from "@/hooks/queries";
import { useToast } from "@/stores/toast";
import { Badge, Button, Card, CardTitle, PageHeader } from "@/components/ui";
import { QueryBoundary, errorMessage } from "@/components/common";
import { ExecutionsTable } from "./executions/ExecutionsTable";

export function AutomationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const wf = useWorkflow(id);
  const executions = useExecutions({ workflow_id: id, limit: 20 });
  const m = useWorkflowMutations();
  const toast = useToast();

  const nodes = (wf.data?.nodes ?? []) as Array<{ name?: string; type?: string }>;

  async function run() {
    if (!id) return;
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
        title={wf.data?.name ?? "Workflow"}
        description={<Link to="/automations" className="text-brand hover:underline">← All automations</Link>}
        actions={
          wf.data && (
            <>
              <Button
                variant="outline"
                onClick={() =>
                  (wf.data!.active ? m.deactivate.mutateAsync(id!) : m.activate.mutateAsync(id!))
                    .then(() => {
                      toast.success("Updated");
                      wf.refetch();
                    })
                    .catch((e) => toast.error("Failed", errorMessage(e)))
                }
              >
                {wf.data.active ? "Deactivate" : "Activate"}
              </Button>
              <Button variant="ghost" onClick={run}>
                Run
              </Button>
            </>
          )
        }
      />

      <QueryBoundary isLoading={wf.isLoading} isError={wf.isError} error={wf.error} onRetry={() => wf.refetch()}>
        {wf.data && (
          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardTitle>Overview</CardTitle>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted">Status</dt>
                  <dd>
                    <Badge tone={wf.data.active ? "success" : "neutral"}>{wf.data.active ? "active" : "inactive"}</Badge>
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">ID</dt>
                  <dd className="font-mono text-xs">{wf.data.id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">Nodes</dt>
                  <dd>{nodes.length}</dd>
                </div>
              </dl>
            </Card>

            <Card className="lg:col-span-2">
              <CardTitle>Nodes</CardTitle>
              <ul className="max-h-64 space-y-1 overflow-auto text-sm">
                {nodes.map((n, i) => (
                  <li key={i} className="flex items-center justify-between border-b border-border py-1.5 last:border-0">
                    <span className="text-fg">{n.name ?? "unnamed"}</span>
                    <span className="font-mono text-[11px] text-muted">{n.type}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        )}
      </QueryBoundary>

      <Card className="mt-4">
        <CardTitle action={<Link to={`/executions?workflow_id=${id}`} className="text-xs text-brand hover:underline">All</Link>}>
          Recent executions
        </CardTitle>
        <ExecutionsTable query={executions} compact />
      </Card>
    </div>
  );
}
