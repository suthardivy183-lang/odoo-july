import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  icon: Icon,
  hint,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  icon: LucideIcon;
  hint?: string;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="flex items-center gap-4 p-5">
        <div
          className={cn(
            "flex h-11 w-11 shrink-0 items-center justify-center rounded-lg",
            tone === "default" && "bg-primary/10 text-primary",
            tone === "success" && "bg-emerald-500/12 text-emerald-600 dark:text-emerald-400",
            tone === "warning" && "bg-amber-500/12 text-amber-600 dark:text-amber-400",
            tone === "danger" && "bg-red-500/12 text-red-600 dark:text-red-400",
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="text-2xl font-bold leading-tight">{value}</p>
          {hint && <p className="truncate text-xs text-muted-foreground">{hint}</p>}
        </div>
      </CardContent>
    </Card>
  );
}
