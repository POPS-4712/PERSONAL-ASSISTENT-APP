import { useMemo, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/stores/auth";
import { useHealth } from "@/hooks/queries";
import { Button, Card, Input, Badge } from "@/components/ui";
import { API_URL, API_URL_IS_DEFAULT } from "@/config";

/** Mirrors the backend policy in app/schemas/auth.py (password_min_length = 10). */
function passwordProblem(pw: string): string | null {
  if (pw.length < 10) return "At least 10 characters.";
  if (pw === pw.toLowerCase() || pw === pw.toUpperCase() || !/\d/.test(pw))
    return "Needs an upper-case letter, a lower-case letter and a digit.";
  return null;
}

export function RegisterPage() {
  const { register, error, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const health = useHealth();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [touched, setTouched] = useState(false);

  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  const pwProblem = useMemo(() => passwordProblem(password), [password]);
  const mismatch = confirm.length > 0 && confirm !== password;
  const canSubmit = !!email && username.length >= 3 && !pwProblem && !mismatch;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    clearError();
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      await register(email.trim(), username.trim(), password);
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
          <h1 className="text-lg font-semibold text-fg">Create your account</h1>
          <p className="text-sm text-muted">The first account becomes the administrator</p>
        </div>

        <Card>
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <Input
              label="Email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
            <Input
              label="Username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              hint="3–64 chars: letters, digits, . _ -"
              error={touched && username.length > 0 && username.length < 3 ? "Too short." : undefined}
              required
            />
            <Input
              label="Password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              hint={!password ? "Min 10 chars, with upper, lower and a digit." : undefined}
              error={touched && pwProblem ? pwProblem : undefined}
              required
            />
            <Input
              label="Confirm password"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              error={mismatch ? "Passwords do not match." : undefined}
              required
            />

            {error && (
              <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" loading={submitting} disabled={submitting || (touched && !canSubmit)}>
              Create account
            </Button>
          </form>
        </Card>

        <p className="mt-4 text-center text-sm text-muted">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-brand hover:underline">
            Sign in
          </Link>
        </p>

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
