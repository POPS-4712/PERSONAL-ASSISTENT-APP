import type { FC, SVGProps } from "react";
import {
  IconBolt,
  IconDashboard,
  IconKey,
  IconList,
  IconProfiles,
  IconPulse,
  IconSettings,
  IconShield,
  IconTerminal,
} from "@/components/icons";

export interface NavItem {
  to: string;
  label: string;
  icon: FC<SVGProps<SVGSVGElement>>;
  admin?: boolean;
}

export const primaryNav: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: IconDashboard },
  { to: "/profiles", label: "Profiles", icon: IconProfiles },
  { to: "/credentials", label: "Credentials", icon: IconKey },
  { to: "/automations", label: "Automations", icon: IconBolt },
  { to: "/executions", label: "Executions", icon: IconList },
  { to: "/monitoring", label: "Monitoring", icon: IconPulse },
  { to: "/logs", label: "Logs", icon: IconTerminal },
  { to: "/settings", label: "Settings", icon: IconSettings },
];

export const adminNav: NavItem[] = [
  { to: "/admin/users", label: "Users", icon: IconProfiles, admin: true },
  { to: "/admin/system", label: "System", icon: IconDashboard, admin: true },
  { to: "/admin/security", label: "Security", icon: IconShield, admin: true },
];
