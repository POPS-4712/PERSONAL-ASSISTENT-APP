import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Navigate, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@/stores/theme";
import { ToastProvider } from "@/stores/toast";
import { AuthProvider } from "@/stores/auth";
import { PublicOnly, RequireAuth } from "@/router";
import { Toaster } from "@/components/ui";
import { DashboardPage } from "./DashboardPage";
import { AutomationsPage } from "./AutomationsPage";
import { ProfilesPage } from "./ProfilesPage";
import { CredentialsPage } from "./CredentialsPage";
import { makeQueryClient, installFetchStub, sampleUser, sampleToken } from "@/test/utils";
import { setSession } from "@/api/tokenStore";

function wrap(ui: React.ReactElement, route = "/") {
  return render(
    <ThemeProvider>
      <QueryClientProvider client={makeQueryClient()}>
        <ToastProvider>
          <AuthProvider>
            <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
            <Toaster />
          </AuthProvider>
        </ToastProvider>
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

const healthOk = { status: "ok", version: "0.1.0", environment: "testing", database: "ok", problems: [] };
const statusOk = {
  operational: true,
  state: "operational",
  degraded_services: [],
  services: [{ name: "postgres", kind: "tcp", target: "postgres:5432", online: true, detail: "ok", latency_ms: 2 }],
  checked_at: new Date().toISOString(),
};
const metricsOk = {
  cpu_percent: 23,
  memory_percent: 48,
  memory_used_mb: 4096,
  memory_total_mb: 8192,
  disk_percent: 42,
  disk_free_gb: 100,
  disk_total_gb: 200,
  load_avg_1m: 0.5,
  uptime_seconds: 7200,
  sampled_at: new Date().toISOString(),
};

beforeEach(() => {
  setSession(null);
  vi.unstubAllGlobals();
});

function GuardHarness({ route }: { route: string }) {
  return wrap(
    <Routes>
      <Route element={<PublicOnly />}>
        <Route path="/login" element={<div>LOGIN SCREEN</div>} />
      </Route>
      <Route element={<RequireAuth />}>
        <Route path="/dashboard" element={<div>DASHBOARD SCREEN</div>} />
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>,
    route,
  );
}

describe("routing guards", () => {
  it("redirects an anonymous visit to /dashboard to the login screen", async () => {
    installFetchStub({});
    GuardHarness({ route: "/dashboard" });
    expect(await screen.findByText("LOGIN SCREEN")).toBeInTheDocument();
  });

  it("sends an authenticated user away from /login", async () => {
    setSession({ ...sampleToken(), expires_at: Date.now() + 60_000 });
    installFetchStub({ "GET /api/auth/me": { body: sampleUser } });
    GuardHarness({ route: "/login" });
    expect(await screen.findByText("DASHBOARD SCREEN")).toBeInTheDocument();
  });
});

describe("DashboardPage", () => {
  it("renders live metrics from the backend", async () => {
    installFetchStub({
      "GET /api/health": { body: healthOk },
      "GET /api/system/status": { body: statusOk },
      "GET /api/system/metrics": { body: metricsOk },
      "GET /api/n8n/health": { body: { base_url: "x", api_key_configured: true, reachable: true } },
      "GET /api/n8n/workflows": { body: { data: [{ id: "w1", name: "Asistente - Email", active: true }] } },
    });
    wrap(<DashboardPage />);
    expect(await screen.findByText("42%")).toBeInTheDocument(); // disk
    expect(await screen.findByText("Asistente - Email")).toBeInTheDocument();
  });

  it("shows an offline banner when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    wrap(<DashboardPage />);
    expect(
      await screen.findByText("Unable to connect to the Automation Center backend.", {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });
});

describe("AutomationsPage", () => {
  it("explains that Run is unavailable when the backend returns 501", async () => {
    setSession({ ...sampleToken(), expires_at: Date.now() + 60_000 });
    installFetchStub({
      "GET /api/n8n/health": { body: { base_url: "x", api_key_configured: true, reachable: true, api_key_valid: true } },
      "GET /api/n8n/workflows": { body: { data: [{ id: "w1", name: "Asistente - Noticias", active: false, updatedAt: new Date().toISOString() }] } },
      "POST /api/n8n/workflows/w1/run": { status: 501, body: { detail: { code: "n8n_unsupported", message: "no execute endpoint" } } },
    });
    wrap(<AutomationsPage />);
    const runBtn = await screen.findByRole("button", { name: "Run" });
    await userEvent.click(runBtn);
    expect(await screen.findByText("Run unavailable")).toBeInTheDocument();
  });

  it("shows the n8n offline empty state", async () => {
    setSession({ ...sampleToken(), expires_at: Date.now() + 60_000 });
    installFetchStub({
      "GET /api/n8n/health": { body: { base_url: "x", api_key_configured: true, reachable: false, detail: "connection refused" } },
      "GET /api/n8n/workflows": { status: 502, body: { detail: { code: "n8n_unavailable", message: "down" } } },
    });
    wrap(<AutomationsPage />);
    expect(await screen.findByText("n8n is offline")).toBeInTheDocument();
  });
});

describe("empty states", () => {
  it("Profiles shows a first-run empty state", async () => {
    setSession({ ...sampleToken(), expires_at: Date.now() + 60_000 });
    installFetchStub({
      "GET /api/profiles": { body: [] },
      "GET /api/profiles/dimensions": { body: { dimensions: ["sector"], note: "open object" } },
    });
    wrap(<ProfilesPage />);
    expect(await screen.findByText("No profiles yet.")).toBeInTheDocument();
  });

  it("Credentials shows the not-configured store warning", async () => {
    setSession({ ...sampleToken(), expires_at: Date.now() + 60_000 });
    installFetchStub({
      "GET /api/credentials": { body: [] },
      "GET /api/credentials/store-status": { body: { configured: false } },
    });
    wrap(<CredentialsPage />);
    expect(await screen.findByText(/credential store is not configured/i)).toBeInTheDocument();
  });
});
