import type { RouteObject } from "react-router-dom";

import { RequireRole } from "@/app/require-role";
import { CarbonAccountingPage } from "@/features/carbon-accounting/carbon-accounting-page";
import { MissionControlPage } from "@/features/mission-control/mission-control-page";
import { RiskHeatmapPage } from "@/features/risk-heatmap/risk-heatmap-page";
import { DigitalTwinPage } from "@/features/digital-twin/digital-twin-page";

/**
 * Track A routes — master data, environmental, governance, scoring, reports,
 * settings pages. APPEND routes here from Track A only; Track B never edits
 * this file (see TEAM_PLAN.md).
 */
export const routesTrackA: RouteObject[] = [
  {
    path: "digital-twin",
    element: (
      <RequireRole roles={["esg_manager"]}>
        <DigitalTwinPage />
      </RequireRole>
    ),
  },
  {
    path: "mission-control",
    element: (
      <RequireRole roles={["dept_head", "esg_manager", "admin"]}>
        <MissionControlPage />
      </RequireRole>
    ),
  },
  { path: "carbon-accounting", element: <CarbonAccountingPage /> },
  { path: "risk-heatmap", element: <RiskHeatmapPage /> },
];
