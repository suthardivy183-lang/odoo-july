import { Coins } from "lucide-react";

import type { NavItem } from "@/app/nav-types";

/**
 * Track A navigation — master data, environmental, governance, scoring,
 * reports, settings. APPEND items here from Track A only; Track B never
 * edits this file (see TEAM_PLAN.md).
 */
export const navTrackA: NavItem[] = [
  {
    to: "/carbon-accounting",
    label: "Carbon Cost Accounting",
    icon: Coins,
    group: "Overview",
    roles: ["admin", "esg_manager", "dept_head"],
  },
];

