import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { cn } from "@/utils/cn";
import { useAuth } from "@/stores/auth";
import { useTheme } from "@/stores/theme";
import { useHealth } from "@/hooks/queries";
import { Badge, Button } from "@/components/ui";
import { IconLogout, IconMenu, IconMoon, IconSun, IconX } from "@/components/icons";
import { adminNav, primaryNav, type NavItem } from "./nav";
import { APP_ENV } from "@/config";

function NavList({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5">
      {items.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
              isActive ? "bg-brand/10 text-brand" : "text-muted hover:bg-surface-2 hover:text-fg",
            )
          }
        >
          <Icon />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2 px-2">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-brand-fg">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M6 18 10 6l3 8 2-4 4 8" />
        </svg>
      </span>
      <div className="leading-tight">
        <p className="text-sm font-semibold text-fg">Automation Center</p>
        <p className="text-[11px] text-muted">{APP_ENV}</p>
      </div>
    </div>
  );
}

export function AppLayout() {
  const { user, logout, isAdmin } = useAuth();
  const { theme, toggle } = useTheme();
  const health = useHealth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const backendState = health.isError
    ? { tone: "danger" as const, label: "Backend offline" }
    : health.data
      ? health.data.status === "ok"
        ? { tone: "success" as const, label: "Operational" }
        : { tone: "warning" as const, label: "Degraded" }
      : { tone: "neutral" as const, label: "Checking…" };

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-screen bg-bg">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-surface p-3 lg:flex">
        <div className="py-2">
          <Brand />
        </div>
        <div className="mt-4 flex-1 overflow-y-auto">
          <NavList items={primaryNav} />
          {isAdmin && (
            <>
              <p className="mt-5 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted">Admin</p>
              <div className="mt-1">
                <NavList items={adminNav} />
              </div>
            </>
          )}
        </div>
        <div className="rounded-lg border border-border bg-surface-2 p-3 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted">System</span>
            <Badge tone={backendState.tone}>{backendState.label}</Badge>
          </div>
          {health.data?.version && (
            <p className="mt-1 text-muted">backend v{health.data.version}</p>
          )}
        </div>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 top-0 flex h-full w-72 flex-col border-r border-border bg-surface p-3">
            <div className="flex items-center justify-between py-2">
              <Brand />
              <button onClick={() => setMobileOpen(false)} aria-label="Close menu" className="p-2 text-muted">
                <IconX />
              </button>
            </div>
            <div className="mt-4 flex-1 overflow-y-auto">
              <NavList items={primaryNav} onNavigate={() => setMobileOpen(false)} />
              {isAdmin && (
                <>
                  <p className="mt-5 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted">Admin</p>
                  <NavList items={adminNav} onNavigate={() => setMobileOpen(false)} />
                </>
              )}
            </div>
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-surface/80 px-4 py-3 backdrop-blur">
          <button
            className="p-2 text-muted lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <IconMenu />
          </button>
          <div className="flex flex-1 items-center gap-2">
            <Badge tone={backendState.tone}>{backendState.label}</Badge>
          </div>
          <button
            onClick={toggle}
            className="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-fg"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? <IconSun /> : <IconMoon />}
          </button>
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-fg">{user?.username}</p>
            <p className="text-xs text-muted">{user?.role}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={handleLogout} aria-label="Sign out">
            <IconLogout />
          </Button>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
