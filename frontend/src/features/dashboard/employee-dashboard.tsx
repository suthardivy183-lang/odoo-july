import { useQuery } from "@tanstack/react-query";
import {
  Award,
  Bell,
  CheckCircle2,
  FileSignature,
  Flame,
  HeartHandshake,
  Target,
  Trophy,
} from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/app/empty-state";
import { PageHeader } from "@/components/app/page-header";
import { StatCard } from "@/components/app/stat-card";
import { StatusChip } from "@/components/app/status-chip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  ChallengeParticipationOut,
  EmployeeDashboardOut,
  UserBadgeOut,
} from "@/lib/types";

export function EmployeeDashboard() {
  const { user } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["employee-dashboard"],
    queryFn: () => api.get<EmployeeDashboardOut>("/dashboards/employee"),
  });
  const { data: myChallenges } = useQuery({
    queryKey: ["my-challenge-participations"],
    queryFn: () => api.get<ChallengeParticipationOut[]>("/challenges/participations/me"),
  });
  const { data: myBadges } = useQuery({
    queryKey: ["my-badges"],
    queryFn: () => api.get<UserBadgeOut[]>("/badges/me"),
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

  const inFlight = (myChallenges ?? []).filter((p) =>
    ["joined", "submitted", "resubmission_requested"].includes(p.status),
  );

  return (
    <div>
      <PageHeader
        title={`Hi ${user?.full_name.split(" ")[0]} 👋`}
        description="Your impact, challenges and rewards at a glance."
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="XP Balance" value={data.xp_balance} icon={Flame}
          hint={`${data.lifetime_earned} lifetime earned`} />
        <StatCard label="Leaderboard Rank" value={data.my_rank ? `#${data.my_rank}` : "—"}
          icon={Trophy} hint="All-time, shared ranks on ties" tone="success" />
        <StatCard label="Badges" value={data.badges_count} icon={Award} tone="warning"
          hint="Unlocked so far" />
        <StatCard
          label="Approved Wins"
          value={data.approved_challenges + data.approved_csr}
          icon={CheckCircle2}
          hint={`${data.approved_challenges} challenges · ${data.approved_csr} CSR`}
          tone="success"
        />
      </div>

      {(data.pending_policy_acks > 0 || data.unread_notifications > 0) && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {data.pending_policy_acks > 0 && (
            <Card className="border-amber-500/40 bg-amber-500/5">
              <CardContent className="flex items-center justify-between gap-3 p-4">
                <div className="flex items-center gap-3">
                  <FileSignature className="h-5 w-5 text-amber-600" />
                  <p className="text-sm">
                    <span className="font-semibold">{data.pending_policy_acks} policy</span>{" "}
                    acknowledgement{data.pending_policy_acks > 1 ? "s" : ""} pending
                  </p>
                </div>
                <Button size="sm" variant="outline" asChild>
                  <Link to="/policies">Review</Link>
                </Button>
              </CardContent>
            </Card>
          )}
          {data.unread_notifications > 0 && (
            <Card>
              <CardContent className="flex items-center justify-between gap-3 p-4">
                <div className="flex items-center gap-3">
                  <Bell className="h-5 w-5 text-primary" />
                  <p className="text-sm">
                    <span className="font-semibold">{data.unread_notifications}</span> unread
                    notification{data.unread_notifications > 1 ? "s" : ""}
                  </p>
                </div>
                <Button size="sm" variant="outline" asChild>
                  <Link to="/notifications">Open</Link>
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Target className="h-4 w-4 text-primary" /> My active challenges
            </CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link to="/challenges">Browse all</Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {inFlight.length === 0 ? (
              <EmptyState
                icon={Target}
                title="No active challenges"
                description={`${data.active_challenges_open} challenges are open right now — join one and start earning XP.`}
                action={
                  <Button size="sm" asChild>
                    <Link to="/challenges">Explore challenges</Link>
                  </Button>
                }
              />
            ) : (
              inFlight.slice(0, 5).map((p) => (
                <div key={p.id} className="rounded-lg border p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-medium">{p.challenge_title}</p>
                    <StatusChip status={p.status} />
                  </div>
                  <div className="flex items-center gap-3">
                    <Progress value={p.progress} className="flex-1" />
                    <span className="w-10 text-right text-xs text-muted-foreground">
                      {p.progress}%
                    </span>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Award className="h-4 w-4 text-primary" /> Latest badges
            </CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link to="/badges">All badges</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {(myBadges ?? []).length === 0 ? (
              <EmptyState
                icon={Award}
                title="No badges yet"
                description="Complete challenges and CSR activities to unlock badges."
              />
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {(myBadges ?? []).slice(0, 6).map((b) => (
                  <div key={b.id} className="flex items-center gap-2.5 rounded-lg border p-2.5">
                    <span className="text-2xl">{b.badge.icon}</span>
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold">{b.badge.name}</p>
                      <p className="text-[11px] text-muted-foreground">
                        {new Date(b.awarded_at).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                        })}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Card className="transition-shadow hover:shadow-md">
          <Link to="/csr">
            <CardContent className="flex items-center gap-4 p-5">
              <HeartHandshake className="h-8 w-8 text-primary" />
              <div>
                <p className="font-semibold">{data.active_csr_open} CSR activities open</p>
                <p className="text-sm text-muted-foreground">
                  Volunteer, upload proof and earn points
                </p>
              </div>
            </CardContent>
          </Link>
        </Card>
        <Card className="transition-shadow hover:shadow-md">
          <Link to="/rewards">
            <CardContent className="flex items-center gap-4 p-5">
              <Flame className="h-8 w-8 text-primary" />
              <div>
                <p className="font-semibold">Spend your {data.xp_balance} points</p>
                <p className="text-sm text-muted-foreground">Browse the rewards store</p>
              </div>
            </CardContent>
          </Link>
        </Card>
      </div>
    </div>
  );
}
