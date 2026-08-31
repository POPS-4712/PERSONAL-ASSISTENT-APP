import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  credentialsApi,
  n8nApi,
  profilesApi,
  systemApi,
  type CredentialInput,
  type ProfileInput,
} from "@/api";

export const qk = {
  health: ["health"] as const,
  systemStatus: ["system", "status"] as const,
  systemMetrics: ["system", "metrics"] as const,
  logs: (params: Record<string, unknown>) => ["logs", params] as const,
  profiles: ["profiles"] as const,
  profile: (id: string) => ["profiles", id] as const,
  profileDimensions: ["profiles", "dimensions"] as const,
  credentials: ["credentials"] as const,
  credentialStore: ["credentials", "store-status"] as const,
  n8nHealth: ["n8n", "health"] as const,
  workflows: ["n8n", "workflows"] as const,
  workflow: (id: string) => ["n8n", "workflows", id] as const,
  executions: (params: Record<string, unknown>) => ["n8n", "executions", params] as const,
};

/* ------------------------------- system ------------------------------- */

export function useHealth() {
  return useQuery({
    queryKey: qk.health,
    queryFn: ({ signal }) => systemApi.health(signal),
    refetchInterval: 20_000,
    retry: 1,
  });
}

export function useSystemStatus(enabled = true) {
  return useQuery({
    queryKey: qk.systemStatus,
    queryFn: ({ signal }) => systemApi.status(signal),
    refetchInterval: 15_000,
    enabled,
    retry: 1,
  });
}

export function useSystemMetrics(enabled = true) {
  return useQuery({
    queryKey: qk.systemMetrics,
    queryFn: ({ signal }) => systemApi.metrics(signal),
    refetchInterval: 15_000,
    enabled,
    retry: 1,
  });
}

export function useLogsBacklog(params: { level?: string; limit?: number; source?: string }) {
  return useQuery({
    queryKey: qk.logs(params),
    queryFn: () => systemApi.logs(params),
    retry: 1,
  });
}

/* ------------------------------ profiles ------------------------------ */

export function useProfiles() {
  return useQuery({ queryKey: qk.profiles, queryFn: profilesApi.list });
}

export function useProfile(id: string | undefined) {
  return useQuery({
    queryKey: qk.profile(id ?? ""),
    queryFn: () => profilesApi.get(id as string),
    enabled: !!id,
  });
}

export function useProfileDimensions() {
  return useQuery({
    queryKey: qk.profileDimensions,
    queryFn: profilesApi.dimensions,
    staleTime: 5 * 60_000,
  });
}

export function useProfileMutations() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: qk.profiles });
  };
  return {
    create: useMutation({ mutationFn: (input: ProfileInput) => profilesApi.create(input), onSuccess: invalidate }),
    update: useMutation({
      mutationFn: (v: { id: string; input: Parameters<typeof profilesApi.update>[1] }) =>
        profilesApi.update(v.id, v.input),
      onSuccess: (_d, v) => {
        invalidate();
        qc.invalidateQueries({ queryKey: qk.profile(v.id) });
      },
    }),
    duplicate: useMutation({
      mutationFn: (v: { id: string; name?: string }) => profilesApi.duplicate(v.id, v.name),
      onSuccess: invalidate,
    }),
    remove: useMutation({ mutationFn: (id: string) => profilesApi.remove(id), onSuccess: invalidate }),
    activate: useMutation({ mutationFn: (id: string) => profilesApi.activate(id), onSuccess: invalidate }),
    deactivate: useMutation({ mutationFn: (id: string) => profilesApi.deactivate(id), onSuccess: invalidate }),
    setPrimary: useMutation({ mutationFn: (id: string) => profilesApi.setPrimary(id), onSuccess: invalidate }),
  };
}

/* ----------------------------- credentials ---------------------------- */

export function useCredentials() {
  return useQuery({ queryKey: qk.credentials, queryFn: credentialsApi.list });
}

export function useCredentialStore() {
  return useQuery({ queryKey: qk.credentialStore, queryFn: credentialsApi.storeStatus, staleTime: 60_000 });
}

export function useCredentialMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: qk.credentials });
  return {
    create: useMutation({ mutationFn: (input: CredentialInput) => credentialsApi.create(input), onSuccess: invalidate }),
    update: useMutation({
      mutationFn: (v: { id: string; input: Parameters<typeof credentialsApi.update>[1] }) =>
        credentialsApi.update(v.id, v.input),
      onSuccess: invalidate,
    }),
    remove: useMutation({ mutationFn: (id: string) => credentialsApi.remove(id), onSuccess: invalidate }),
    test: useMutation({
      mutationFn: (id: string) => credentialsApi.test(id),
      onSuccess: invalidate,
    }),
  };
}

/* -------------------------------- n8n -------------------------------- */

export function useN8nHealth() {
  return useQuery({ queryKey: qk.n8nHealth, queryFn: n8nApi.health, refetchInterval: 30_000, retry: 0 });
}

export function useWorkflows() {
  return useQuery({ queryKey: qk.workflows, queryFn: () => n8nApi.workflows({ limit: 200 }), retry: 0 });
}

export function useWorkflow(id: string | undefined) {
  return useQuery({
    queryKey: qk.workflow(id ?? ""),
    queryFn: () => n8nApi.workflow(id as string),
    enabled: !!id,
    retry: 0,
  });
}

export function useExecutions(params: { workflow_id?: string; status?: string; limit?: number }) {
  return useQuery({
    queryKey: qk.executions(params),
    queryFn: () => n8nApi.executions(params),
    retry: 0,
    refetchInterval: 20_000,
  });
}

export function useWorkflowMutations() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: qk.workflows });
  };
  return {
    activate: useMutation({ mutationFn: (id: string) => n8nApi.activate(id), onSuccess: invalidate }),
    deactivate: useMutation({ mutationFn: (id: string) => n8nApi.deactivate(id), onSuccess: invalidate }),
    run: useMutation({ mutationFn: (id: string) => n8nApi.run(id) }),
  };
}
