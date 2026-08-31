import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/stores/auth";
import { useHealth } from "@/hooks/queries";
import { Button, Card, Input, Badge } from "@/components/ui";
import { API_URL, API_URL_IS_DEFAULT } from "@/config";

export function LoginPage() {
  const { login, error, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const health = useHealth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    clearError();
    setSubmitting(true);
    try {
      await login(identifier.trim(), password);
      navigate(from, { replace: true });
    } catch {
      /* error surfaced via context */
    } finally {
      setSubmitting(false);
    }
  }

  const backendReachable = !health.isError;

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand text-brand-fg">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 18 10 6l3 8 2-4 4 8" />
            </svg>
          </span>
          <h1 className="text-lg font-semibold text-fg">Automation Center</h1>
          <p className="text-sm text-muted">Sign in to your control plane</p>
        </div>

        <Card>
          <form onSubmit={onSubmit} className="space-y-4">
            <Input
              label="Email or username"
              autoComplete="username"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              required
              autoFocus
            />
            <Input
              label="Password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            {error && (
              <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" loading={submitting} disabled={!identifier || !password}>
              Sign in
            </Button>
          </form>
        </Card>

        <div className="mt-4 flex items-center justify-center gap-2 text-xs text-muted">
          <Badge tone={backendReachable ? "success" : "danger"}>
            {backendReachable ? "Backend reachable" : "Backend unreachable"}
          </Badge>
          <span className="truncate" title={API_URL}>
            {API_URL}
          </span>
        </div>
        {API_URL_IS_DEFAULT && (
          <p className="mt-2 text-center text-[11px] text-muted">
            Using the local-dev default. Set <code>VITE_API_URL</code> for other environments.
          </p>
        )}
      </div>
    </div>
  );
}
