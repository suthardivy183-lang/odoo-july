import type { LucideIcon } from "lucide-react";

import type { Role } from "@/lib/types";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  group: string;
  /** Roles that see this item; null = every authenticated user. Admin always sees everything. */
  roles: Role[] | null;
}
