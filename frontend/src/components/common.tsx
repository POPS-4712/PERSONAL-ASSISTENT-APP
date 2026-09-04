import type { ReactNode } from "react";
import { ApiError } from "@/api";
import type { ServiceStatus } from "@/api/types";
import { cn } from "@/utils/cn";
import { relativeTime } from "@/utils/format";
import { ErrorState, SkeletonRows, StatusDot } from "@/components/ui";

/** Turn an unknown error into a user-facing message (no stack traces in prod). */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "network" || err.status === 0) return "Cannot reach the Automation Center backend.";
    return err.message;
  }
  if (err instanceof Error && import.meta.env.DEV) return err.message;
  return "Unexpected error.";
}

export function QueryBoundary({
  isLoading,
  isError,
  error,
  onRetry,
  children,
  skeletonRows = 4,
}: {
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  onRetry?: () => void;
  children: ReactNode;
  skeletonRows?: number;
}) {
  if (isLoading) return <SkeletonRows rows={skeletonRows} />;
  if (isError) return <ErrorState description={errorMessage(error)} onRetry={onRetry} />;
  return <>{children}</>;
}

export function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: "ok" | "warn" | "danger" | "brand";
}) {
  return (
    <div className="card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p
        className={cn(
          "mt-1 text-2xl font-semibold tabular-nums",
          accent === "ok" && "text-ok",
          accent === "warn" && "text-warn",
          accent === "danger" && "text-danger",
          accent === "brand" && "text-brand",
          !accent && "text-fg",
        )}
      >
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
    </div>
  );
}

/** Resolve the display status. `status` (4-state) wins; fall back to the legacy
 *  boolean/null `online` for any caller that hasn't been updated. */
function resolveStatus(status: ServiceStatus | undefined, online: boolean | null): ServiceStatus {
  if (status) return status;
  return online == null ? "unknown" : online ? "online" : "offline";
}

export const STATUS_META: Record<
  ServiceStatus,
  { label: string; className: string; dot: boolean | null }
> = {
  online: { label: "online", className: "text-ok", dot: true },
  // "configured" is the healthy state for things you cannot ping: profile data
  // in Postgres, an API key the provider accepts.
  configured: { label: "configured", className: "text-ok", dot: true },
  // reachable but only partly usable - amber, because it is not an outage and
  // not health either
  degraded: { label: "degraded", className: "text-warn", dot: false },
  invalid: { label: "invalid", className: "text-danger", dot: false },
  offline: { label: "offline", className: "text-danger", dot: false },
  // deliberately grey, not red: nobody asked for this service here
  not_configured: { label: "not configured", className: "text-muted", dot: null },
  unknown: { label: "unknown", className: "text-muted", dot: null },
};

export function ServiceRow({
  name,
  status,
  online,
  latency,
  detail,
  checkedAt,
}: {
  name: string;
  status?: ServiceStatus;
  online?: boolean | null;
  detail?: string;
  latency?: number | null;
  checkedAt?: string | null;
}) {
  const resolved = resolveStatus(status, online ?? null);
  const meta = STATUS_META[resolved];
  const isProblem = resolved === "offline" || resolved === "invalid" || resolved === "degraded";
  return (
    <div className="border-b border-border py-2.5 last:border-0">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <StatusDot online={meta.dot} />
          <span className="text-sm font-medium capitalize text-fg">{name}</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted">
          {latency != null && <span className="tabular-nums">{latency} ms</span>}
          {checkedAt && <span className="tabular-nums">{relativeTime(checkedAt)}</span>}
          <span className={cn("font-semibold uppercase", meta.className)}>{meta.label}</span>
        </div>
      </div>
      {detail && (
        <p className={cn("mt-1 pl-6 text-xs", isProblem ? "text-danger" : "text-muted")}>{detail}</p>
      )}
    </div>
  );
}
