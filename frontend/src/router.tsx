import { createBrowserRouter, Navigate, Outlet, useLocation, type RouteObject } from "react-router-dom";
import { useAuth } from "@/stores/auth";
import { Spinner } from "@/components/ui";
import { AppLayout } from "@/layouts/AppLayout";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ProfilesPage } from "@/pages/ProfilesPage";
import { ProfileDetailPage } from "@/pages/ProfileDetailPage";
import { CredentialsPage } from "@/pages/CredentialsPage";
import { AutomationsPage } from "@/pages/AutomationsPage";
import { AutomationDetailPage } from "@/pages/AutomationDetailPage";
import { ExecutionsPage } from "@/pages/ExecutionsPage";
import { MonitoringPage } from "@/pages/MonitoringPage";
import { LogsPage } from "@/pages/LogsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SetupPage } from "@/pages/SetupPage";
import { AdminUsersPage, AdminSecurityPage, AdminSystemPage } from "@/pages/AdminPages";
import { NotFoundPage } from "@/pages/NotFoundPage";

function FullScreenLoader() {
  return (
    <div className="flex h-screen items-center justify-center bg-bg text-brand">
      <Spinner className="h-8 w-8" />
    </div>
  );
}

export function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <FullScreenLoader />;
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

export function RequireAdmin() {
  const { isAdmin, status } = useAuth();
  if (status === "loading") return <FullScreenLoader />;
  if (!isAdmin) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}

export function PublicOnly() {
  const { status } = useAuth();
  if (status === "loading") return <FullScreenLoader />;
  if (status === "authenticated") return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}

export const routes: RouteObject[] = [
  {
    element: <PublicOnly />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
    ],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: "dashboard", element: <DashboardPage /> },
          { path: "profiles", element: <ProfilesPage /> },
          { path: "profiles/:id", element: <ProfileDetailPage /> },
          { path: "credentials", element: <CredentialsPage /> },
          { path: "automations", element: <AutomationsPage /> },
          { path: "automations/:id", element: <AutomationDetailPage /> },
          { path: "executions", element: <ExecutionsPage /> },
          { path: "monitoring", element: <MonitoringPage /> },
          { path: "logs", element: <LogsPage /> },
          { path: "settings", element: <SettingsPage /> },
          { path: "setup", element: <SetupPage /> },
          {
            path: "admin",
            element: <RequireAdmin />,
            children: [
              { index: true, element: <Navigate to="/admin/users" replace /> },
              { path: "users", element: <AdminUsersPage /> },
              { path: "system", element: <AdminSystemPage /> },
              { path: "security", element: <AdminSecurityPage /> },
            ],
          },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter(routes);
