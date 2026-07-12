import { useAuth } from "@/lib/auth";

import { EmployeeDashboard } from "./employee-dashboard";
import { HeadDashboard } from "./head-dashboard";

export function DashboardPage() {
  const { user } = useAuth();
  if (user?.role === "dept_head" || user?.role === "esg_manager" || user?.role === "admin") {
    return <HeadDashboard />;
  }
  return <EmployeeDashboard />;
}
