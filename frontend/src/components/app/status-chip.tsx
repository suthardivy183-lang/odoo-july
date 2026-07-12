import { Badge } from "@/components/ui/badge";
import { titleCase } from "@/lib/utils";

const STATUS_VARIANTS: Record<string, "success" | "warning" | "destructive" | "info" | "muted" | "default"> = {
  active: "success",
  approved: "success",
  completed: "info",
  fulfilled: "success",
  published: "success",
  resolved: "success",
  open: "warning",
  in_progress: "info",
  joined: "info",
  submitted: "warning",
  under_review: "warning",
  resubmission_requested: "warning",
  placed: "info",
  pending: "warning",
  draft: "muted",
  archived: "muted",
  inactive: "muted",
  closed: "muted",
  rejected: "destructive",
  cancelled: "destructive",
  returned: "warning",
  overdue: "destructive",
  low: "muted",
  medium: "info",
  high: "warning",
  critical: "destructive",
  easy: "success",
  hard: "destructive",
};

export function StatusChip({ status }: { status: string }) {
  return <Badge variant={STATUS_VARIANTS[status] ?? "default"}>{titleCase(status)}</Badge>;
}
