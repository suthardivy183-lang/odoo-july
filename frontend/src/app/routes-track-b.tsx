import type { RouteObject } from "react-router-dom";

import { RequireRole } from "@/app/require-role";
import { ApprovalsPage } from "@/features/approvals/approvals-page";
import { BadgesPage } from "@/features/badges/badges-page";
import { CategoriesPage } from "@/features/categories/categories-page";
import { ChallengesPage } from "@/features/challenges/challenges-page";
import { CSRPage } from "@/features/csr/csr-page";
import { DashboardPage } from "@/features/dashboard/dashboard-page";
import { LeaderboardPage } from "@/features/gamification/leaderboard-page";
import { XPHistoryPage } from "@/features/gamification/xp-history-page";
import { NotificationsPage } from "@/features/notifications/notifications-page";
import { RewardsPage } from "@/features/rewards/rewards-page";

/** Track B routes — engagement & gamification. Do not edit from Track A. */
export const routesTrackB: RouteObject[] = [
  { index: true, element: <DashboardPage /> },
  { path: "csr", element: <CSRPage /> },
  { path: "challenges", element: <ChallengesPage /> },
  { path: "leaderboard", element: <LeaderboardPage /> },
  { path: "rewards", element: <RewardsPage /> },
  { path: "badges", element: <BadgesPage /> },
  { path: "xp", element: <XPHistoryPage /> },
  {
    path: "approvals",
    element: (
      <RequireRole roles={["dept_head", "esg_manager"]}>
        <ApprovalsPage />
      </RequireRole>
    ),
  },
  {
    path: "manage/categories",
    element: (
      <RequireRole roles={["esg_manager"]}>
        <CategoriesPage />
      </RequireRole>
    ),
  },
  { path: "notifications", element: <NotificationsPage /> },
];
