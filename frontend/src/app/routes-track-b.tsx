import type { RouteObject } from "react-router-dom";

import { ChallengesPage } from "@/features/challenges/challenges-page";
import { CSRPage } from "@/features/csr/csr-page";
import { DashboardPage } from "@/features/dashboard/dashboard-page";

/** Track B routes — engagement & gamification. Do not edit from Track A. */
export const routesTrackB: RouteObject[] = [
  { index: true, element: <DashboardPage /> },
  { path: "csr", element: <CSRPage /> },
  { path: "challenges", element: <ChallengesPage /> },
];
