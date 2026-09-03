import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { AuthProvider, useAuth } from "./auth";
import { ToastProvider } from "./toast";
import { setSession } from "@/api/tokenStore";
import { authEvents } from "@/api/client";
import { sampleToken, sampleUser } from "@/test/utils";

function Probe() {
  const { status, user, isAdmin, login, register, logout, error } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user">{user?.username ?? "-"}</span>
      <span data-testid="admin">{String(isAdmin)}</span>
      <span data-testid="error">{error ?? "-"}</span>
      <button onClick={() => void login("admin", "pw").catch(() => {})}>login</button>
      <button onClick={() => void register("a@b.co", "admin", "Passw0rd!!").catch(() => {})}>register</button>
      <button onClick={() => logout()}>logout</button>
    </div>
  );
}

function renderProbe() {
  return render(
    <ToastProvider>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </ToastProvider>,
  );
}

beforeEach(() => {
  setSession(null);
  vi.unstubAllGlobals();
});

describe("AuthProvider", () => {
  it("starts anonymous with no stored session", () => {
    renderProbe();
    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
  });

  it("logs in, stores the session and exposes the admin flag", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(sampleToken()), { status: 200 })));
    renderProbe();

    await act(async () => {
      screen.getByText("login").click();
    });

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(screen.getByTestId("user")).toHaveTextContent("admin");
    expect(screen.getByTestId("admin")).toHaveTextContent("true");
  });

  it("registers, stores the session and authenticates", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(sampleToken()), { status: 201 })),
    );
    renderProbe();
    await act(async () => {
      screen.getByText("register").click();
    });
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(screen.getByTestId("user")).toHaveTextContent("admin");
  });

  it("surfaces a friendly message when the email/username is taken (409)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "email or username already in use" }), { status: 409 })),
    );
    renderProbe();
    await act(async () => {
      screen.getByText("register").click();
    });
    await waitFor(() =>
      expect(screen.getByTestId("error")).toHaveTextContent("already registered"),
    );
  });

  it("surfaces a friendly message on 401", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "bad" }), { status: 401 })));
    renderProbe();
    await act(async () => {
      screen.getByText("login").click();
    });
    await waitFor(() =>
      expect(screen.getByTestId("error")).toHaveTextContent("Incorrect email/username or password."),
    );
  });

  it("validates a persisted session via /auth/me on boot", async () => {
    setSession({ ...sampleToken(), expires_at: Date.now() + 1000, access_token: "a", refresh_token: "r" });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(sampleUser), { status: 200 })));
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
  });

  it("goes anonymous when the API layer emits 'expired'", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(sampleToken()), { status: 200 })));
    renderProbe();
    await act(async () => {
      screen.getByText("login").click();
    });
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));

    act(() => {
      setSession(null);
      authEvents.dispatchEvent(new Event("expired"));
    });
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(screen.getByTestId("error")).toHaveTextContent("session has expired");
  });
});
