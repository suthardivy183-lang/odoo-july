import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bell, ChevronRight, RefreshCw, Users } from "lucide-react";
import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";

import { PageHeader } from "@/components/app/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  DeptScore,
  DeptScoreDetail,
  DomainEventOut,
  OrgScore,
  Page,
  ScorePeriod,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const PERIODS: { value: ScorePeriod; label: string }[] = [
  { value: "month", label: "Month" },
  { value: "quarter", label: "Quarter" },
  { value: "fy", label: "FY" },
  { value: "all", label: "All time" },
];

/** Higher score = better = greener. Returns a chart hex color. */
function scoreHex(score: number | null): string {
  if (score === null) return "#94a3b8";
  if (score >= 80) return "#10b981";
  if (score >= 65) return "#84cc16";
  if (score >= 50) return "#f59e0b";
  if (score >= 35) return "#f97316";
  return "#ef4444";
}

function scoreClasses(score: number | null): string {
  if (score === null)
    return "text-slate-500 bg-slate-500/10 border-slate-500/20";
  if (score >= 80)
    return "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
  if (score >= 65)
    return "text-lime-600 dark:text-lime-400 bg-lime-500/10 border-lime-500/20";
  if (score >= 50)
    return "text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/20";
  if (score >= 35)
    return "text-orange-600 dark:text-orange-400 bg-orange-500/10 border-orange-500/20";
  return "text-red-600 dark:text-red-400 bg-red-500/10 border-red-500/20";
}

const fmt = (v: number | null) => (v === null ? "—" : v.toFixed(1));

function timeAgo(iso: string): string {
  const secs = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

// --- Org score gauge ---------------------------------------------------------

function OrgGauge({ score, grade }: { score: number | null; grade: string }) {
  const value = score ?? 0;
  const data = [{ name: "score", value, fill: scoreHex(score) }];
  return (
    <div className="relative mx-auto h-52 w-52">
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          innerRadius="76%"
          outerRadius="100%"
          data={data}
          startAngle={90}
          endAngle={-270}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
          <RadialBar background dataKey="value" cornerRadius={30} angleAxisId={0} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-5xl font-bold tracking-tight">{fmt(score)}</span>
        <span className="text-xs uppercase tracking-widest text-muted-foreground">
          out of 100
        </span>
        <span
          className={cn(
            "mt-2 rounded-full border px-3 py-0.5 text-sm font-bold",
            scoreClasses(score),
          )}
        >
          Grade {grade}
        </span>
      </div>
    </div>
  );
}

// --- Pillar card with sparkline ---------------------------------------------

function PillarCard({
  label,
  value,
  weight,
  spark,
}: {
  label: string;
  value: number | null;
  weight: number;
  spark: { x: string; y: number | null }[];
}) {
  const hex = scoreHex(value);
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {label}
            </p>
            <p className="mt-1 text-3xl font-bold" style={{ color: hex }}>
              {fmt(value)}
            </p>
          </div>
          <Badge variant="secondary" className="text-[10px]">
            weight {weight}%
          </Badge>
        </div>
        <div className="mt-2 h-10">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={spark}>
              <Line
                type="monotone"
                dataKey="y"
                stroke={hex}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

// --- Department strip row ----------------------------------------------------

function DeptRow({ dept, onOpen }: { dept: DeptScore; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-muted/50"
    >
      <span
        className={cn(
          "flex h-11 w-12 shrink-0 items-center justify-center rounded-md border text-sm font-bold",
          scoreClasses(dept.total),
        )}
      >
        {fmt(dept.total)}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{dept.department_name}</p>
        <p className="text-xs text-muted-foreground">
          E {fmt(dept.environmental)} · S {fmt(dept.social)} · G {fmt(dept.governance)}
          <span className="ml-1">· {dept.employee_count} staff</span>
        </p>
      </div>
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
    </button>
  );
}

// --- Drill-down "explain the math" dialog -----------------------------------

const PILLAR_OF: Record<string, string> = {
  goal_completion: "Environmental",
  emission_performance: "Environmental",
  csr_participation: "Social",
  diversity_balance: "Social",
  training_completion: "Social",
  policy_ack: "Governance",
  audit_score: "Governance",
  compliance_health: "Governance",
};

function DrillDown({
  departmentId,
  period,
  onClose,
}: {
  departmentId: number;
  period: ScorePeriod;
  onClose: () => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["score-dept", departmentId, period],
    queryFn: () =>
      api.get<DeptScoreDetail>(`/scores/departments/${departmentId}?period=${period}`),
  });

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        {isLoading || !data ? (
          <div className="space-y-3 py-6">
            <Skeleton className="h-8 w-1/2" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <>
            <DialogHeader>
              <div className="flex items-center justify-between pr-6">
                <DialogTitle className="text-xl">
                  {data.department.department_name}
                </DialogTitle>
                <span
                  className={cn(
                    "rounded-full border px-3 py-1 text-sm font-bold",
                    scoreClasses(data.department.total),
                  )}
                >
                  {fmt(data.department.total)} · Grade {data.grade}
                </span>
              </div>
              <DialogDescription>
                How each pillar and component builds this department's ESG score.
              </DialogDescription>
            </DialogHeader>

            <div className="grid grid-cols-3 gap-3 pt-2">
              {(["environmental", "social", "governance"] as const).map((k) => (
                <div key={k} className="rounded-lg border p-3 text-center">
                  <p className="text-[11px] font-bold uppercase text-muted-foreground">{k}</p>
                  <p
                    className="text-2xl font-bold"
                    style={{ color: scoreHex(data.department[k]) }}
                  >
                    {fmt(data.department[k])}
                  </p>
                </div>
              ))}
            </div>

            <div className="mt-2 space-y-2">
              {data.department.components.map((c) => (
                <div
                  key={c.key}
                  className="flex items-start justify-between gap-3 rounded-lg border p-3"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-semibold">
                      {c.label}
                      <span className="ml-2 text-[10px] font-medium uppercase text-muted-foreground">
                        {PILLAR_OF[c.key]}
                      </span>
                    </p>
                    <p className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                      {c.value === null ? (
                        <span className="italic">No data this period — excluded from the pillar</span>
                      ) : (
                        Object.entries(c.inputs).map(([key, val]) => (
                          <span key={key}>
                            {key.replace(/_/g, " ")}: <b>{String(val)}</b>
                          </span>
                        ))
                      )}
                    </p>
                  </div>
                  <span
                    className={cn(
                      "shrink-0 rounded-md border px-2 py-1 text-xs font-bold",
                      scoreClasses(c.value),
                    )}
                  >
                    {c.value === null ? "—" : c.value.toFixed(0)}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// --- Live activity ticker ----------------------------------------------------

function humanizeEvent(e: DomainEventOut): string {
  const p = e.payload || {};
  switch (e.type) {
    case "carbon.txn.created":
      return `${Number(p.co2e_kg ?? 0).toFixed(0)} kgCO₂e recorded — ${p.description ?? "carbon transaction"}`;
    case "carbon.budget.exceeded":
      return `Carbon budget exceeded (${Number(p.utilization_pct ?? 0).toFixed(0)}% used)`;
    case "risk.alert.raised":
      return `Risk alert: ${String(p.alert_type ?? "").replace(/_/g, " ")}`;
    case "participation.approved":
      return `${p.kind ?? "activity"} approved — +${p.xp ?? 0} XP`;
    case "compliance.issue.created":
      return `New compliance issue opened`;
    case "compliance.issue.status_changed":
      return `Compliance issue → ${p.status ?? "updated"}`;
    case "score.updated":
      return `ESG score recomputed — org now ${p.org_total ?? "—"}`;
    default:
      return e.type.replace(/[._]/g, " ");
  }
}

function ActivityTicker() {
  const { data, isError } = useQuery({
    queryKey: ["events-recent"],
    queryFn: () => api.get<DomainEventOut[]>("/events/recent?limit=15"),
    refetchInterval: 5000,
    retry: false,
  });

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center gap-2">
        <Activity className="h-4 w-4 text-primary" />
        <CardTitle className="text-base">Live activity</CardTitle>
      </CardHeader>
      <CardContent>
        {isError ? (
          <p className="text-sm text-muted-foreground">
            The event stream lights up once the event bus is connected. Actions across
            the platform will appear here in real time.
          </p>
        ) : !data || data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No recent activity.</p>
        ) : (
          <ul className="space-y-2.5">
            {data.map((e) => (
              <li key={e.id} className="flex items-start gap-2.5 text-sm">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <div className="min-w-0 flex-1">
                  <p className="truncate">{humanizeEvent(e)}</p>
                  <p className="text-xs text-muted-foreground">{timeAgo(e.created_at)}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// --- Alerts rail -------------------------------------------------------------

function AlertsRail() {
  const { data } = useQuery({
    queryKey: ["mc-risk-alerts"],
    queryFn: () => api.get<Page<any>>("/risk-heatmap/alerts?size=8"),
    refetchInterval: 5000,
  });
  const items = data?.items ?? [];
  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center gap-2">
        <Bell className="h-4 w-4 text-amber-500" />
        <CardTitle className="text-base">Risk alerts</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No active risk alerts.</p>
        ) : (
          <ul className="space-y-2.5">
            {items.map((a) => (
              <li key={a.id} className="rounded-lg border p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold">{a.department_name}</span>
                  <Badge variant="outline" className="text-[10px]">
                    {String(a.alert_type).replace(/_/g, " ")}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{a.message}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// --- Page --------------------------------------------------------------------

export function MissionControlPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const [period, setPeriod] = useState<ScorePeriod>("fy");
  const [drillId, setDrillId] = useState<number | null>(null);
  const canRecalc = hasRole("esg_manager");

  const { data: org, isLoading: orgLoading } = useQuery({
    queryKey: ["score-org", period],
    queryFn: () => api.get<OrgScore>(`/scores/organization?period=${period}`),
    refetchInterval: 5000,
  });

  const { data: depts } = useQuery({
    queryKey: ["score-depts", period],
    queryFn: () => api.get<DeptScore[]>(`/scores/departments?period=${period}`),
    refetchInterval: 5000,
  });

  const recalc = useMutation({
    mutationFn: () => api.post(`/scores/recalculate?period=${period}`),
    onSuccess: () => {
      toast.success("ESG scores recalculated");
      qc.invalidateQueries({ queryKey: ["score-org"] });
      qc.invalidateQueries({ queryKey: ["score-depts"] });
    },
    onError: (e: any) => toast.error(e?.message ?? "Recalculation failed"),
  });

  const trend = org?.trend ?? [];
  const prevTotal = trend.length > 1 ? trend[trend.length - 2].total_score : null;
  const delta =
    org?.total != null && prevTotal != null ? org.total - prevTotal : null;
  const spark = (key: "environmental_score" | "social_score" | "governance_score") =>
    trend.map((t) => ({ x: t.snapshot_date, y: t[key] }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="ESG Mission Control"
        description="The live nervous system of your organization — one score, every pillar, updating in real time."
        actions={
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border p-0.5">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => setPeriod(p.value)}
                  className={cn(
                    "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                    period === p.value
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {p.label}
                </button>
              ))}
            </div>
            {canRecalc && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => recalc.mutate()}
                disabled={recalc.isPending}
              >
                <RefreshCw
                  className={cn("mr-1.5 h-3.5 w-3.5", recalc.isPending && "animate-spin")}
                />
                Recalculate
              </Button>
            )}
          </div>
        }
      />

      {/* Hero: gauge + pillars */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Organization ESG score</CardTitle>
          </CardHeader>
          <CardContent>
            {orgLoading || !org ? (
              <Skeleton className="mx-auto h-52 w-52 rounded-full" />
            ) : (
              <>
                <OrgGauge score={org.total} grade={org.grade} />
                <div className="mt-3 flex items-center justify-center gap-2 text-sm">
                  {delta === null ? (
                    <span className="text-muted-foreground">
                      {org.dept_count} departments scored
                    </span>
                  ) : (
                    <span
                      className={cn(
                        "font-semibold",
                        delta >= 0 ? "text-emerald-600" : "text-red-600",
                      )}
                    >
                      {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)} vs last snapshot
                    </span>
                  )}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-3 lg:col-span-2">
          {orgLoading || !org ? (
            Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32" />)
          ) : (
            <>
              <PillarCard
                label="Environmental"
                value={org.environmental}
                weight={org.weights.environmental}
                spark={spark("environmental_score")}
              />
              <PillarCard
                label="Social"
                value={org.social}
                weight={org.weights.social}
                spark={spark("social_score")}
              />
              <PillarCard
                label="Governance"
                value={org.governance}
                weight={org.weights.governance}
                spark={spark("governance_score")}
              />
            </>
          )}
        </div>
      </div>

      {/* Trend */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Fiscal-year ESG score history</CardTitle>
        </CardHeader>
        <CardContent className="h-72">
          {orgLoading || !org ? (
            <Skeleton className="h-full w-full" />
          ) : trend.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              No score history yet — run a recalculation to start the trend.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend}>
                <defs>
                  <linearGradient id="mcScore" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                <XAxis
                  dataKey="snapshot_date"
                  fontSize={11}
                  tickFormatter={(d) =>
                    new Date(d).toLocaleDateString(undefined, { month: "short" })
                  }
                />
                <YAxis fontSize={11} domain={[0, 100]} />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="total_score"
                  name="ESG score"
                  stroke="#10b981"
                  strokeWidth={2}
                  fill="url(#mcScore)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Departments + rails */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center gap-2">
            <Users className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">Departments by ESG score</CardTitle>
          </CardHeader>
          <CardContent>
            {!depts ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : depts.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No departments with active employees to score.
              </p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {depts.map((d) => (
                  <DeptRow
                    key={d.department_id}
                    dept={d}
                    onOpen={() => setDrillId(d.department_id)}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-4">
          <ActivityTicker />
          <AlertsRail />
        </div>
      </div>

      {drillId !== null && (
        <DrillDown
          departmentId={drillId}
          period={period}
          onClose={() => setDrillId(null)}
        />
      )}
    </div>
  );
}
