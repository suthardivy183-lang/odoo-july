import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Target, Users, Zap } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/app/empty-state";
import { FileUpload } from "@/components/app/file-upload";
import { PageHeader } from "@/components/app/page-header";
import { Pager } from "@/components/app/pager";
import { StatusChip } from "@/components/app/status-chip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import type { ChallengeOut, ChallengeParticipationOut, Page } from "@/lib/types";
import { formatDate, formatDateTime } from "@/lib/utils";

const PAGE_SIZE = 12;

function ChallengeCard({ challenge, onOpen }: { challenge: ChallengeOut; onOpen: () => void }) {
  return (
    <Card
      className="cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-md"
      onClick={onOpen}
    >
      <CardContent className="p-4">
        <div className="mb-2 flex items-start justify-between gap-2">
          <Badge variant="secondary">{challenge.category_name}</Badge>
          <StatusChip status={challenge.difficulty} />
        </div>
        <p className="font-semibold leading-snug">{challenge.title}</p>
        <div className="mt-3 space-y-1 text-xs text-muted-foreground">
          <p className="flex items-center gap-1.5">
            <CalendarDays className="h-3.5 w-3.5" /> Deadline {formatDate(challenge.deadline)}
          </p>
          <p className="flex items-center gap-1.5">
            <Users className="h-3.5 w-3.5" /> {challenge.participant_count} participating ·
            unlimited spots
          </p>
        </div>
        <div className="mt-3 flex items-center justify-between">
          <p className="flex items-center gap-1 text-sm font-bold text-primary">
            <Zap className="h-4 w-4" /> {challenge.xp} XP
          </p>
          <StatusChip status={challenge.my_participation_status ?? challenge.status} />
        </div>
        {challenge.my_progress != null && challenge.my_participation_status === "joined" && (
          <div className="mt-2 flex items-center gap-2">
            <Progress value={challenge.my_progress} className="flex-1" />
            <span className="text-xs text-muted-foreground">{challenge.my_progress}%</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ChallengeDialog({
  challenge,
  onClose,
}: {
  challenge: ChallengeOut | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const join = useMutation({
    mutationFn: () => api.post(`/challenges/${challenge!.id}/join`),
    onSuccess: () => {
      toast.success("Challenge joined — good luck!");
      void qc.invalidateQueries({ queryKey: ["challenges"] });
      onClose();
    },
    onError: (e) => toast.error(e.message),
  });
  if (!challenge) return null;
  const joinable =
    ["active", "under_review"].includes(challenge.status) && !challenge.my_participation_id;
  const evidenceLabel = {
    required: "Proof required",
    not_required: "No proof needed",
    inherit: "Follows organisation evidence policy",
  }[challenge.evidence];
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{challenge.category_name}</Badge>
            <StatusChip status={challenge.difficulty} />
            <StatusChip status={challenge.status} />
          </div>
          <DialogTitle className="pt-1">{challenge.title}</DialogTitle>
          <DialogDescription>{challenge.description}</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-xs text-muted-foreground">Reward</p>
            <p className="font-bold text-primary">{challenge.xp} XP</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Deadline</p>
            <p className="font-medium">{formatDate(challenge.deadline)}</p>
          </div>
          <div className="col-span-2">
            <p className="text-xs text-muted-foreground">Evidence</p>
            <p className="font-medium">{evidenceLabel}</p>
          </div>
        </div>
        {joinable && (
          <Button className="w-full" disabled={join.isPending} onClick={() => join.mutate()}>
            {join.isPending ? "Joining…" : "Join challenge"}
          </Button>
        )}
        {challenge.my_participation_id && (
          <p className="rounded-lg bg-accent px-3 py-2 text-center text-sm text-accent-foreground">
            You are in — update progress under “My challenges”.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function MyChallenges() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["challenges", "mine"],
    queryFn: () => api.get<ChallengeParticipationOut[]>("/challenges/participations/me"),
  });
  const setProgress = useMutation({
    mutationFn: ({ id, progress }: { id: number; progress: number }) =>
      api.post(`/challenges/participations/${id}/progress`, { progress }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["challenges"] }),
    onError: (e) => toast.error(e.message),
  });
  const attachProof = useMutation({
    mutationFn: ({ id, attachmentId }: { id: number; attachmentId: number }) =>
      api.post(`/challenges/participations/${id}/proof`, { attachment_id: attachmentId }),
    onSuccess: () => {
      toast.success("Proof submitted for review");
      void qc.invalidateQueries({ queryKey: ["challenges"] });
    },
    onError: (e) => toast.error(e.message),
  });

  if (isLoading) return <Skeleton className="h-40" />;
  if (!data?.length) {
    return (
      <EmptyState
        icon={Target}
        title="No challenges joined"
        description="Pick a challenge from the Explore tab and start earning XP."
      />
    );
  }
  return (
    <div className="space-y-3">
      {data.map((p) => (
        <Card key={p.id}>
          <CardContent className="p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-semibold">{p.challenge_title}</p>
                <p className="text-xs text-muted-foreground">
                  Joined {formatDate(p.created_at)}
                  {p.xp_awarded != null && (
                    <span className="ml-2 font-semibold text-primary">
                      +{p.xp_awarded} XP awarded
                    </span>
                  )}
                </p>
              </div>
              <StatusChip status={p.status} />
            </div>
            {["joined", "resubmission_requested"].includes(p.status) && (
              <div className="mt-3 space-y-3 border-t pt-3">
                <div className="flex items-center gap-3">
                  <Progress value={p.progress} className="flex-1" />
                  <span className="w-10 text-right text-xs">{p.progress}%</span>
                  <Select
                    className="w-24"
                    value=""
                    onChange={(e) => {
                      if (e.target.value !== "")
                        setProgress.mutate({ id: p.id, progress: Number(e.target.value) });
                    }}
                  >
                    <option value="">Set…</option>
                    {[10, 25, 50, 75, 90, 100].map((v) => (
                      <option key={v} value={v}>
                        {v}%
                      </option>
                    ))}
                  </Select>
                </div>
                <FileUpload
                  context="proof"
                  onUploaded={(attachmentId) => attachProof.mutate({ id: p.id, attachmentId })}
                />
              </div>
            )}
            {p.status === "submitted" && (
              <div className="mt-2 flex items-center gap-3">
                <Progress value={p.progress} className="flex-1" />
                <span className="text-xs text-muted-foreground">
                  {p.progress}% · awaiting review
                </span>
              </div>
            )}
            {p.approver_comment && (
              <p className="mt-2 rounded-md bg-muted px-3 py-2 text-xs">
                <span className="font-semibold">{p.approver?.full_name ?? "Approver"}:</span>{" "}
                {p.approver_comment}
                {p.decided_at && (
                  <span className="text-muted-foreground"> · {formatDateTime(p.decided_at)}</span>
                )}
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function ChallengesPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [selected, setSelected] = useState<ChallengeOut | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["challenges", "list", page, status, difficulty],
    queryFn: () =>
      api.get<Page<ChallengeOut>>(
        `/challenges?page=${page}&size=${PAGE_SIZE}` +
          (status ? `&status=${status}` : "") +
          (difficulty ? `&difficulty=${difficulty}` : ""),
      ),
  });

  return (
    <div>
      <PageHeader
        title="Challenges"
        description="Sustainability missions with XP rewards. Draft → Active → Under review → Completed."
      />
      <Tabs defaultValue="explore">
        <TabsList>
          <TabsTrigger value="explore">Explore</TabsTrigger>
          <TabsTrigger value="mine">My challenges</TabsTrigger>
        </TabsList>
        <TabsContent value="explore">
          <div className="mb-4 flex flex-wrap gap-2">
            <Select
              className="max-w-40"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="under_review">Under review</option>
              <option value="completed">Completed</option>
            </Select>
            <Select
              className="max-w-40"
              value={difficulty}
              onChange={(e) => {
                setDifficulty(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Any difficulty</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </Select>
          </div>
          {isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-44" />
              ))}
            </div>
          ) : !data?.items.length ? (
            <EmptyState icon={Target} title="No challenges found" />
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {data.items.map((c) => (
                  <ChallengeCard key={c.id} challenge={c} onOpen={() => setSelected(c)} />
                ))}
              </div>
              <Pager page={page} size={PAGE_SIZE} total={data.total} onPage={setPage} />
            </>
          )}
        </TabsContent>
        <TabsContent value="mine">
          <MyChallenges />
        </TabsContent>
      </Tabs>
      <ChallengeDialog challenge={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
