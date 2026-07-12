import type { RouteObject } from "react-router-dom";

import { RequireRole } from "@/app/require-role";
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
];
