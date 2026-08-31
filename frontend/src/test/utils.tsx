import type { ReactElement, ReactNode } from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ThemeProvider } from "@/stores/theme";
import { ToastProvider } from "@/stores/toast";
import { AuthProvider } from "@/stores/auth";
import { Toaster } from "@/components/ui";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function AllProviders({
  children,
  route = "/",
  client,
}: {
  children: ReactNode;
  route?: string;
  client?: QueryClient;
}) {
  const qc = client ?? makeQueryClient();
  return (
    <ThemeProvider>
      <QueryClientProvider client={qc}>
        <ToastProvider>
          <AuthProvider>
            <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
            <Toaster />
          </AuthProvider>
        </ToastProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export function renderWithProviders(
  ui: ReactElement,
  opts: { route?: string; client?: QueryClient } & Omit<RenderOptions, "wrapper"> = {},
) {
  const { route, client, ...rest } = opts;
  return render(ui, {
    wrapper: ({ children }) => (
      <AllProviders route={route} client={client}>
        {children}
      </AllProviders>
    ),
    ...rest,
  });
}

/** Minimal typed fetch stub. Routes are matched by `METHOD path` prefix. */
export interface StubRoute {
  status?: number;
  body?: unknown;
  headers?: Record<string, string>;
}

export function installFetchStub(routes: Record<string, StubRoute | ((url: string, init?: RequestInit) => StubRoute)>) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const stub = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = (init?.method ?? "GET").toUpperCase();
    const path = new URL(url).pathname;
    calls.push({ url, init });

    const key = Object.keys(routes)
      .sort((a, b) => b.length - a.length)
      .find((k) => {
        const [m, p] = k.split(" ");
        return m === method && path.startsWith(p);
      });
    const entry = key ? routes[key] : undefined;
    const resolved = typeof entry === "function" ? entry(url, init) : entry;
    if (!resolved) {
      return new Response(JSON.stringify({ detail: "not stubbed" }), { status: 404, headers: { "content-type": "application/json" } });
    }
    return new Response(resolved.body === undefined ? "" : JSON.stringify(resolved.body), {
      status: resolved.status ?? 200,
      headers: { "content-type": "application/json", ...resolved.headers },
    });
  });
  vi.stubGlobal("fetch", stub);
  return { stub, calls };
}

export const sampleUser = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "admin@example.com",
  username: "admin",
  role: "admin" as const,
  status: "active" as const,
  last_login_at: null,
};

export function sampleToken(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    access_token: "access-123",
    refresh_token: "refresh-123",
    token_type: "bearer",
    expires_in: 1800,
    user: sampleUser,
    ...overrides,
  };
}
