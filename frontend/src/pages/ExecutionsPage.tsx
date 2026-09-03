import { useSearchParams } from "react-router-dom";
import { n8nStateOf, useExecutions, useN8nHealth, useWorkflows } from "@/hooks/queries";
import { EmptyState, PageHeader, Select } from "@/components/ui";
import { ExecutionsTable } from "./executions/ExecutionsTable";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "success", label: "Success" },
  { value: "error", label: "Failed" },
  { value: "waiting", label: "Waiting" },
];

export function ExecutionsPage() {
  const [params, setParams] = useSearchParams();
  const workflowId = params.get("workflow_id") ?? "";
  const status = params.get("status") ?? "";

  const n8n = useN8nHealth();
  const workflows = useWorkflows();
  const executions = useExecutions({
    workflow_id: workflowId || undefined,
    status: status || undefined,
    limit: 100,
  });

  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  const n8nState = n8nStateOf(n8n.data, n8n.isError);

  return (
    <div>
      <PageHeader title="Executions" description="Workflow run history from n8n." />

      {n8nState === "not_configured" ? (
        <EmptyState
          title="n8n is not configured"
          description="Set AC_N8N_BASE_URL and AC_N8N_API_KEY on the backend to see execution history."
        />
      ) : n8nState === "offline" ? (
        <EmptyState title="n8n is offline" description="Execution history is temporarily unavailable." />
      ) : (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-2 md:max-w-xl">
            <Select label="Workflow" value={workflowId} onChange={(e) => update("workflow_id", e.target.value)}>
              <option value="">All workflows</option>
              {workflows.data?.data.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </Select>
            <Select label="Status" value={status} onChange={(e) => update("status", e.target.value)}>
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </div>

          <ExecutionsTable query={executions} />
        </>
      )}
    </div>
  );
}
