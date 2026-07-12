import { Navigate } from "react-router-dom";

import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/types";

export function RequireRole({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { hasRole } = useAuth();
  if (!hasRole(...roles)) return <Navigate to="/" replace />;
  return <>{children}</>;
}
