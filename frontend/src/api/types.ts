/** Response shapes mirrored from the FastAPI backend (app/schemas/*). */

export type UserRole = "admin" | "user";
export type UserStatus = "active" | "disabled" | "pending";

export interface User {
  id: string;
  email: string;
  username: string;
  role: UserRole;
  status: UserStatus;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  environment: string;
  database: string;
  problems: string[];
}

/**
 * `online`         reachable and answering (HTTP / TCP services)
 * `configured`     set up and verified, but not something you can ping
 *                  (profile data in Postgres, an accepted Gemini key)
 * `degraded`       reachable but only partly usable (n8n up, API key rejected)
 * `invalid`        configured with credentials the provider refuses
 * `offline`        configured, but not responding
 * `not_configured` nothing configured here - deliberately NOT an error
 * `unknown`        the probe itself could not run
 */
export type ServiceStatus =
  | "online"
  | "configured"
  | "degraded"
  | "invalid"
  | "offline"
  | "not_configured"
  | "unknown";

export interface ServiceState {
  name: string;
  kind: string;
  target: string;
  status: ServiceStatus;
  /** Back-compat: true for online/configured, false for offline/invalid, else null. */
  online: boolean | null;
  configured?: boolean;
  detail: string;
  latency_ms: number | null;
  checked_at?: string;
  meta?: Record<string, unknown>;
}

export interface SystemStatus {
  operational: boolean;
  state: "operational" | "degraded";
  degraded_services: string[];
  not_configured_services: string[];
  services: ServiceState[];
  checked_at: string;
}

export interface HostMetrics {
  cpu_percent: number;
  memory_percent: number;
  memory_used_mb: number;
  memory_total_mb: number;
  disk_percent: number;
  disk_free_gb: number;
  disk_total_gb: number;
  load_avg_1m: number | null;
  uptime_seconds: number;
  sampled_at: string;
}

export interface LogEntry {
  type: string;
  timestamp: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  source: string;
  message: string;
  correlation_id: string | null;
}

export interface Profile {
  id: string;
  user_id: string;
  name: string;
  description: string;
  configuration: Record<string, unknown>;
  is_primary: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProfileDimensions {
  dimensions: string[];
  note: string;
}

export type CredentialType = "api_key" | "bearer" | "basic_auth" | "oauth2" | "custom";
export type CredentialStatus = "connected" | "error" | "untested" | "disabled";

export interface Credential {
  id: string;
  provider: string;
  name: string;
  type: string;
  status: CredentialStatus;
  hint: string;
  meta: Record<string, unknown>;
  is_enabled: boolean;
  last_tested_at: string | null;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CredentialTestResult {
  ok: boolean;
  detail: string;
  latency_ms: number | null;
  status: string;
}

export interface N8nHealth {
  base_url: string;
  api_key_configured: boolean;
  /** Same vocabulary as the service monitor. Absent on older backends. */
  status?: Extract<ServiceStatus, "online" | "offline" | "not_configured">;
  reachable?: boolean;
  api_key_valid?: boolean;
  detail?: string;
}

export interface N8nWorkflow {
  id: string;
  name: string;
  active: boolean;
  createdAt?: string;
  updatedAt?: string;
  tags?: Array<{ id: string; name: string }>;
  nodes?: Array<Record<string, unknown>>;
  [k: string]: unknown;
}

export interface N8nExecution {
  id: string;
  workflowId?: string;
  finished?: boolean;
  mode?: string;
  status?: string;
  startedAt?: string;
  stoppedAt?: string;
  [k: string]: unknown;
}

export interface Paginated<T> {
  data: T[];
}

/* ------------------------- service configuration ------------------------- */

/** Where the effective configuration came from. */
export type ConfigSource = "database" | "environment" | "none";

/**
 * One integration's configuration as the panel sees it. Never carries the
 * secret itself - only `secret_configured` and a `secret_hint` like "…a3f9".
 */
export interface ServiceConfig {
  service: string;
  label: string;
  configured: boolean;
  enabled: boolean;
  source: ConfigSource;
  base_url: string;
  requires_url: boolean;
  requires_secret: boolean;
  secret_configured: boolean;
  secret_hint: string;
  /** Names of the settings still missing, ready to show to the user. */
  missing: string[];
  last_tested_at: string | null;
  last_test_ok: boolean | null;
  last_test_detail: string;
}

export interface ServiceConfigUpdate {
  base_url?: string;
  /** Omit to keep the stored secret; use `clear_secret` to remove it. */
  secret?: string;
  clear_secret?: boolean;
  enabled?: boolean;
}

export interface ServiceTestResult {
  service: string;
  ok: boolean;
  status: ServiceStatus;
  detail: string;
  latency_ms: number | null;
}

/* --------------------------- profile completeness ------------------------ */

export interface ProfileCompletenessReport {
  profile_id: string;
  name: string;
  complete: boolean;
  filled: string[];
  missing: string[];
  score: number;
}

export interface ProfileCompleteness {
  configured: boolean;
  profile_count: number;
  detail: string;
  required_fields: string[];
  best: ProfileCompletenessReport | null;
}
