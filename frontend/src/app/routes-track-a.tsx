import type { RouteObject } from "react-router-dom";

import { CarbonAccountingPage } from "@/features/carbon-accounting/carbon-accounting-page";

/**
 * Track A routes — master data, environmental, governance, scoring, reports,
 * settings pages. APPEND routes here from Track A only; Track B never edits
 * this file (see TEAM_PLAN.md).
 */
export const routesTrackA: RouteObject[] = [
  { path: "carbon-accounting", element: <CarbonAccountingPage /> },
];

