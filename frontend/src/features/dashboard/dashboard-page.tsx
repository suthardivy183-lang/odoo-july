import { MissionControlPage } from "@/features/mission-control/mission-control-page";
import { useAuth } from "@/lib/auth";

import { EmployeeDashboard } from "./employee-dashboard";
import { HeadDashboard } from "./head-dashboard";

export function DashboardPage() {
  const { user } = useAuth();
  if (user?.role === "esg_manager" || user?.role === "admin") {
    return <MissionControlPage />;
  }
  if (user?.role === "dept_head") {
    return <HeadDashboard />;
  }
  return <EmployeeDashboard />;
}
