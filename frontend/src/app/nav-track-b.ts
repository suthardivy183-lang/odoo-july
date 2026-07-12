import {
  HeartHandshake,
  LayoutDashboard,
  Target,
} from "lucide-react";

import type { NavItem } from "@/app/nav-types";

/** Track B navigation — engagement & gamification. Do not edit from Track A. */
export const navTrackB: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, group: "Overview", roles: null },
  { to: "/csr", label: "CSR Activities", icon: HeartHandshake, group: "Engage", roles: null },
  { to: "/challenges", label: "Challenges", icon: Target, group: "Engage", roles: null },
];
