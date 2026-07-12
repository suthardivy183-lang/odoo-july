import {
  Award,
  Bell,
  CheckSquare,
  Gift,
  HeartHandshake,
  History,
  LayoutDashboard,
  Tags,
  Target,
  Trophy,
} from "lucide-react";

import type { NavItem } from "@/app/nav-types";

/** Track B navigation — engagement & gamification. Do not edit from Track A. */
export const navTrackB: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, group: "Overview", roles: null },
  { to: "/csr", label: "CSR Activities", icon: HeartHandshake, group: "Engage", roles: null },
  { to: "/challenges", label: "Challenges", icon: Target, group: "Engage", roles: null },
  { to: "/leaderboard", label: "Leaderboard", icon: Trophy, group: "Engage", roles: null },
  { to: "/rewards", label: "Rewards", icon: Gift, group: "Earn & Redeem", roles: null },
  { to: "/badges", label: "Badges", icon: Award, group: "Earn & Redeem", roles: null },
  { to: "/xp", label: "XP History", icon: History, group: "Earn & Redeem", roles: null },
  {
    to: "/approvals",
    label: "Approvals",
    icon: CheckSquare,
    group: "Manage",
    roles: ["dept_head"],
  },
  {
    to: "/manage/categories",
    label: "Categories",
    icon: Tags,
    group: "Manage",
    roles: ["esg_manager"],
  },
  { to: "/notifications", label: "Notifications", icon: Bell, group: "System", roles: null },
];
