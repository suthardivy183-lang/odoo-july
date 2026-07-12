import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronRight,
  ShieldAlert,
  Sliders,
  TrendingUp,
  Activity,
  Bell,
  HeartHandshake,
  CheckCircle,
} from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/app/page-header";
import { StatCard } from "@/components/app/stat-card";
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
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export function RiskHeatmapPage() {
  const { user } = useAuth();
  const [drillDept, setDrillDept] = useState<any>(null);

  // Queries
  const { data: heatmap, isLoading: heatmapLoading } = useQuery({
    queryKey: ["risk-heatmap"],
    queryFn: () => api.get<any[]>("/risk-heatmap"),
  });

  const { data: dashboard, isLoading: dashboardLoading } = useQuery({
    queryKey: ["risk-dashboard"],
    queryFn: () => api.get<any>("/risk-heatmap/dashboard"),
  });

  const { data: alerts, isLoading: alertsLoading } = useQuery({
    queryKey: ["risk-alerts"],
    queryFn: () => api.get<any>("/risk-heatmap/alerts"),
  });

  const { data: drilldown, isLoading: drillLoading } = useQuery({
    queryKey: ["risk-drilldown", drillDept?.id],
    queryFn: () => api.get<any>(`/risk-heatmap/drilldown/${drillDept?.id}`),
    enabled: !!drillDept,
  });

  const getRiskColor = (score: number) => {
    if (score <= 30) return "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
    if (score <= 60) return "text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/20";
    if (score <= 80) return "text-orange-600 dark:text-orange-400 bg-orange-500/10 border-orange-500/20";
    return "text-red-600 dark:text-red-400 bg-red-500/10 border-red-500/20";
  };

  const getRiskLabel = (score: number) => {
    if (score <= 30) return "Low Risk";
    if (score <= 60) return "Moderate Risk";
    if (score <= 80) return "High Risk";
    return "Critical Risk";
  };

  const getRiskIndicator = (score: number) => {
    if (score <= 30) return "🟢";
    if (score <= 60) return "🟡";
    if (score <= 80) return "🟠";
    return "🔴";
  };

  const getSeverityBadge = (sev: string) => {
    if (sev === "low") return <Badge variant="secondary">Low</Badge>;
    if (sev === "medium") return <Badge className="bg-amber-500 hover:bg-amber-500">Medium</Badge>;
    if (sev === "high") return <Badge className="bg-orange-500 hover:bg-orange-500">High</Badge>;
    return <Badge variant="destructive">Critical</Badge>;
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="ESG Risk Heatmap"
        description="Continuously monitor and mitigate Environmental, Social, and Governance risk profiles across departments."
      />

      <Tabs defaultValue="matrix" className="space-y-4">
        <TabsList>
          <TabsTrigger value="matrix">Risk Heatmap Matrix</TabsTrigger>
          <TabsTrigger value="dashboard">Risk Dashboard</TabsTrigger>
          <TabsTrigger value="trends">Historical Trends</TabsTrigger>
          <TabsTrigger value="alerts">Risk Alerts Log</TabsTrigger>
        </TabsList>

        {/* MATRIX TAB */}
        <TabsContent value="matrix" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Department Risk Matrix</CardTitle>
            </CardHeader>
            <CardContent>
              {heatmapLoading || !heatmap ? (
                <Skeleton className="h-40 w-full" />
              ) : (
                <div className="relative w-full overflow-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50 font-medium">
                        <th className="p-3">Department</th>
                        <th className="p-3 text-center">Environmental Risk</th>
                        <th className="p-3 text-center">Social Risk</th>
                        <th className="p-3 text-center">Governance Risk</th>
                        <th className="p-3 text-center">Overall Risk</th>
                        <th className="p-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {heatmap.map((dept: any) => (
                        <tr key={dept.id} className="border-b transition-colors hover:bg-muted/50">
                          <td className="p-3 font-semibold">{dept.department_name}</td>
                          <td className="p-3 text-center">
                            <span
                              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${getRiskColor(
                                dept.environmental_risk
                              )}`}
                            >
                              {getRiskIndicator(dept.environmental_risk)} {dept.environmental_risk.toFixed(1)}%
                            </span>
                          </td>
                          <td className="p-3 text-center">
                            <span
                              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${getRiskColor(
                                dept.social_risk
                              )}`}
                            >
                              {getRiskIndicator(dept.social_risk)} {dept.social_risk.toFixed(1)}%
                            </span>
                          </td>
                          <td className="p-3 text-center">
                            <span
                              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${getRiskColor(
                                dept.governance_risk
                              )}`}
                            >
                              {getRiskIndicator(dept.governance_risk)} {dept.governance_risk.toFixed(1)}%
                            </span>
                          </td>
                          <td className="p-3 text-center font-bold">
                            <span
                              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold ${getRiskColor(
                                dept.overall_risk
                              )}`}
                            >
                              {getRiskIndicator(dept.overall_risk)} {dept.overall_risk.toFixed(1)}%
                            </span>
                          </td>
                          <td className="p-3 text-right">
                            <Button size="sm" variant="outline" onClick={() => setDrillDept(dept)}>
                              Drill Down <ChevronRight className="ml-1 h-3.5 w-3.5" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* DASHBOARD TAB */}
        <TabsContent value="dashboard" className="space-y-4">
          {dashboardLoading || !dashboard ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-24" />
              ))}
            </div>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <StatCard
                  label="Highest Risk Department"
                  value={
                    dashboard.highest_risk_department
                      ? `${dashboard.highest_risk_department.name} (${dashboard.highest_risk_department.score.toFixed(1)}%)`
                      : "None"
                  }
                  icon={ShieldAlert}
                  tone="danger"
                />
                <StatCard
                  label="Critical Departments"
                  value={`${dashboard.critical_departments_count}`}
                  icon={AlertTriangle}
                  tone={dashboard.critical_departments_count > 0 ? "danger" : "default"}
                  hint="Score >= 81"
                />
                <StatCard
                  label="Active Risk Drivers"
                  value={`${dashboard.top_risk_drivers.length}`}
                  icon={Sliders}
                  tone="warning"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Top Risk Drivers</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {dashboard.top_risk_drivers.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No active risk drivers identified.</p>
                    ) : (
                      dashboard.top_risk_drivers.map((d: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between border-b pb-2">
                          <span className="text-sm font-semibold">{d.driver}</span>
                          <Badge variant="secondary">{d.count} departments affected</Badge>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Risk Trend & Surges</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {dashboard.departments_with_increasing_risk.length === 0 ? (
                      <div className="flex items-center gap-2 rounded-lg border bg-emerald-500/5 p-4 text-emerald-600">
                        <CheckCircle className="h-5 w-5 shrink-0" />
                        <span className="text-sm font-semibold">No departments showed increasing risk this month.</span>
                      </div>
                    ) : (
                      dashboard.departments_with_increasing_risk.map((d: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between border-b pb-2">
                          <div>
                            <p className="text-sm font-bold">{d.name}</p>
                            <p className="text-xs text-muted-foreground">
                              Increased from {d.previous_score.toFixed(1)}% to {d.current_score.toFixed(1)}%
                            </p>
                          </div>
                          <span className="text-sm font-bold text-red-600">+{d.increase.toFixed(1)}%</span>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Upcoming Compliance Deadlines (14 Days)</CardTitle>
                </CardHeader>
                <CardContent>
                  {dashboard.upcoming_compliance_deadlines.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No upcoming compliance deadlines.</p>
                  ) : (
                    <div className="relative w-full overflow-auto">
                      <table className="w-full text-left text-sm">
                        <thead>
                          <tr className="border-b font-medium">
                            <th className="pb-2">Issue</th>
                            <th className="pb-2">Department</th>
                            <th className="pb-2">Severity</th>
                            <th className="pb-2 text-right">Due Date</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dashboard.upcoming_compliance_deadlines.map((i: any) => (
                            <tr key={i.id} className="border-b py-2">
                              <td className="py-2.5 font-semibold">{i.title}</td>
                              <td className="py-2.5">{i.department_name}</td>
                              <td className="py-2.5">{getSeverityBadge(i.severity)}</td>
                              <td className="py-2.5 text-right font-medium">
                                {new Date(i.due_date).toLocaleDateString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* HISTORICAL TRENDS TAB */}
        <TabsContent value="trends" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Average ESG Risk Trend (6 Months)</CardTitle>
            </CardHeader>
            <CardContent className="h-80">
              {dashboardLoading || !dashboard ? (
                <Skeleton className="h-full w-full" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={dashboard.risk_trend}>
                    <defs>
                      <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#dc2626" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#dc2626" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                    <XAxis dataKey="month" fontSize={11} />
                    <YAxis fontSize={11} domain={[0, 100]} />
                    <Tooltip />
                    <Area
                      type="monotone"
                      dataKey="average_risk"
                      name="Average Risk (%)"
                      stroke="#dc2626"
                      fillOpacity={1}
                      fill="url(#colorRisk)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ALERTS TAB */}
        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Automated Risk Alerts Log</CardTitle>
            </CardHeader>
            <CardContent>
              {alertsLoading || !alerts ? (
                <Skeleton className="h-40 w-full" />
              ) : alerts.items.length === 0 ? (
                <p className="text-sm text-muted-foreground">No risk alerts triggered recently.</p>
              ) : (
                <div className="relative w-full overflow-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50 font-medium">
                        <th className="p-3">Timestamp</th>
                        <th className="p-3">Department</th>
                        <th className="p-3">Alert Type</th>
                        <th className="p-3">Message</th>
                        <th className="p-3 text-right">Risk Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {alerts.items.map((a: any) => (
                        <tr key={a.id} className="border-b transition-colors hover:bg-muted/50">
                          <td className="p-3 text-muted-foreground">
                            {new Date(a.timestamp).toLocaleString()}
                          </td>
                          <td className="p-3 font-semibold">{a.department_name}</td>
                          <td className="p-3">
                            <Badge variant="outline">{a.alert_type.replace("_", " ")}</Badge>
                          </td>
                          <td className="p-3">{a.message}</td>
                          <td className="p-3 text-right font-bold text-red-600">
                            {a.risk_score.toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Drill Down Dialog */}
      <Dialog open={!!drillDept} onOpenChange={(open) => !open && setDrillDept(null)}>
        <DialogContent className="max-w-xl">
          {drillLoading || !drilldown ? (
            <div className="space-y-3 py-6">
              <Skeleton className="h-8 w-1/2" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : (
            <>
              <DialogHeader>
                <div className="flex items-center justify-between pr-6">
                  <DialogTitle className="text-xl">{drillDept.department_name} Drill Down</DialogTitle>
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold ${getRiskColor(
                      drilldown.overall_risk
                    )}`}
                  >
                    {getRiskIndicator(drilldown.overall_risk)} {getRiskLabel(drilldown.overall_risk)} ({drilldown.overall_risk.toFixed(1)}%)
                  </span>
                </div>
                <DialogDescription>ESG detailed risk breakdown and mitigation path.</DialogDescription>
              </DialogHeader>

              <div className="space-y-6 pt-3">
                {/* Pillars score progress bars */}
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border p-3">
                    <p className="text-xs text-muted-foreground uppercase font-bold">Environmental</p>
                    <p className="text-lg font-bold">{drilldown.environmental_risk.toFixed(1)}%</p>
                    <Progress value={drilldown.environmental_risk} className="h-1.5 mt-2" />
                  </div>
                  <div className="rounded-lg border p-3">
                    <p className="text-xs text-muted-foreground uppercase font-bold">Social</p>
                    <p className="text-lg font-bold">{drilldown.social_risk.toFixed(1)}%</p>
                    <Progress value={drilldown.social_risk} className="h-1.5 mt-2" />
                  </div>
                  <div className="rounded-lg border p-3">
                    <p className="text-xs text-muted-foreground uppercase font-bold">Governance</p>
                    <p className="text-lg font-bold">{drilldown.governance_risk.toFixed(1)}%</p>
                    <Progress value={drilldown.governance_risk} className="h-1.5 mt-2" />
                  </div>
                </div>

                {/* AI insights description */}
                <div className="rounded-xl border bg-primary/5 p-4 flex gap-3">
                  <Activity className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-bold text-primary">AI Risk Insights</h4>
                    <p className="text-xs mt-1 text-muted-foreground leading-relaxed">
                      {drilldown.ai_insight}
                    </p>
                  </div>
                </div>

                {/* Contributors & Recommendations */}
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <h4 className="text-sm font-bold text-red-600 flex items-center gap-1.5">
                      <AlertTriangle className="h-4 w-4" /> Risk Contributors
                    </h4>
                    <ul className="mt-2 space-y-1.5 list-disc pl-4 text-xs text-muted-foreground">
                      {drilldown.contributors.map((c: string, idx: number) => (
                        <li key={idx}>{c}</li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h4 className="text-sm font-bold text-emerald-600 flex items-center gap-1.5">
                      <CheckCircle className="h-4 w-4" /> Recommended Actions
                    </h4>
                    <ul className="mt-2 space-y-1.5 list-disc pl-4 text-xs text-muted-foreground">
                      {drilldown.recommendations.map((r: string, idx: number) => (
                        <li key={idx}>{r}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
