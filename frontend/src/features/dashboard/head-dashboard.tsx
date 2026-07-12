import { useQuery } from "@tanstack/react-query";
import { CheckSquare, TrendingUp, Users, Venus } from "lucide-react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageHeader } from "@/components/app/page-header";
import { StatCard } from "@/components/app/stat-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { HeadDashboardOut } from "@/lib/types";
import { titleCase } from "@/lib/utils";

const GENDER_COLORS = ["#15803d", "#65a30d", "#f59e0b"];

export function HeadDashboard() {
  const { user } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["head-dashboard"],
    queryFn: () => api.get<HeadDashboardOut>("/dashboards/head"),
  });

  if (isLoading || !data) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }

  const pending = data.pending_csr_approvals + data.pending_challenge_approvals;
  const scopeLabel =
    user?.role === "dept_head"
      ? `${user.department_name ?? "Department"} (incl. sub-departments)`
      : "Organization-wide";

  return (
    <div>
      <PageHeader
        title={user?.role === "dept_head" ? "Department overview" : "Engagement overview"}
        description={`${scopeLabel} · as of ${data.as_of}`}
        actions={
          pending > 0 ? (
            <Button asChild>
              <Link to="/approvals">
                <CheckSquare /> Review {pending} pending approval{pending > 1 ? "s" : ""}
              </Link>
            </Button>
          ) : undefined
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Team members" value={data.headcount} icon={Users} />
        <StatCard
          label="Pending approvals"
          value={pending}
          icon={CheckSquare}
          hint={`${data.pending_csr_approvals} CSR · ${data.pending_challenge_approvals} challenges`}
          tone={pending > 0 ? "warning" : "success"}
        />
        <StatCard
          label="CSR participation"
          value={`${data.csr_participation_rate}%`}
          icon={TrendingUp}
          hint="Employees with an approved CSR"
          tone="success"
        />
        <StatCard
          label="Challenge completion"
          value={`${data.challenge_completion_rate}%`}
          icon={TrendingUp}
          hint="Employees with an approved challenge"
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Engagement trend (6 months)</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.engagement_trend} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.1} />
                <XAxis dataKey="month" fontSize={11} tickLine={false} />
                <YAxis fontSize={11} tickLine={false} allowDecimals={false} width={28} />
                <Tooltip
                  cursor={{ fill: "rgba(21,128,61,0.06)" }}
                  contentStyle={{ borderRadius: 8, fontSize: 12 }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="csr" name="CSR joins" fill="#15803d" radius={[3, 3, 0, 0]} />
                <Bar dataKey="challenges" name="Challenge joins" fill="#65a30d" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Venus className="h-4 w-4 text-primary" /> Diversity — gender ratio
            </CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.gender_distribution}
                  dataKey="count"
                  nameKey="gender"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                >
                  {data.gender_distribution.map((entry, i) => (
                    <Cell key={entry.gender} fill={GENDER_COLORS[i % GENDER_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number, name: string) => [value, titleCase(name)]}
                  contentStyle={{ borderRadius: 8, fontSize: 12 }}
                />
                <Legend
                  formatter={(value: string) => titleCase(value)}
                  wrapperStyle={{ fontSize: 12 }}
                />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Top performers</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            {data.top_performers.map((p, i) => (
              <div key={p.user.id} className="rounded-lg border p-3">
                <p className="text-xs font-semibold text-primary">#{i + 1}</p>
                <p className="mt-1 truncate text-sm font-medium">{p.user.full_name}</p>
                <p className="truncate text-xs text-muted-foreground">{p.department_name}</p>
                <p className="mt-1 text-sm font-bold">{p.xp_balance} XP</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
