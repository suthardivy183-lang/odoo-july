import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, HeartHandshake, MapPin, Users } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import type { CSRActivityOut, CSRParticipationOut, Page } from "@/lib/types";
import { formatDate, formatDateTime } from "@/lib/utils";

const PAGE_SIZE = 12;

function ActivityCard({ activity, onOpen }: { activity: CSRActivityOut; onOpen: () => void }) {
  const spotsLeft = activity.capacity - activity.joined_count;
  return (
    <Card
      className="cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-md"
      onClick={onOpen}
    >
      <CardContent className="p-4">
        <div className="mb-2 flex items-start justify-between gap-2">
          <Badge variant="secondary">{activity.category_name}</Badge>
          <StatusChip status={activity.my_participation_status ?? activity.status} />
        </div>
        <p className="font-semibold leading-snug">{activity.title}</p>
        <div className="mt-3 space-y-1 text-xs text-muted-foreground">
          <p className="flex items-center gap-1.5">
            <MapPin className="h-3.5 w-3.5" /> {activity.location}
          </p>
          <p className="flex items-center gap-1.5">
            <CalendarDays className="h-3.5 w-3.5" />
            {formatDate(activity.start_date)} – {formatDate(activity.end_date)}
          </p>
          <p className="flex items-center gap-1.5">
            <Users className="h-3.5 w-3.5" />
            {activity.joined_count}/{activity.capacity} joined
            {activity.status === "active" && spotsLeft > 0 && spotsLeft <= 5 && (
              <span className="font-medium text-amber-600">· {spotsLeft} spots left</span>
            )}
          </p>
        </div>
        <p className="mt-3 text-sm font-bold text-primary">+{activity.points} pts</p>
      </CardContent>
    </Card>
  );
}

function ActivityDialog({
  activity,
  onClose,
}: {
  activity: CSRActivityOut | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const join = useMutation({
    mutationFn: () => api.post(`/csr/activities/${activity!.id}/join`),
    onSuccess: () => {
      toast.success("You have joined this activity!");
      void qc.invalidateQueries({ queryKey: ["csr"] });
      onClose();
    },
    onError: (e) => toast.error(e.message),
  });

  if (!activity) return null;
  const isFull = activity.joined_count >= activity.capacity;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{activity.category_name}</Badge>
            <StatusChip status={activity.status} />
          </div>
          <DialogTitle className="pt-1">{activity.title}</DialogTitle>
          <DialogDescription>{activity.description}</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-xs text-muted-foreground">Location</p>
            <p className="font-medium">{activity.location}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Organizer</p>
            <p className="font-medium">{activity.organizer?.full_name ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Dates</p>
            <p className="font-medium">
              {formatDate(activity.start_date)} – {formatDate(activity.end_date)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Capacity</p>
            <p className="font-medium">
              {activity.joined_count}/{activity.capacity}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Points on approval</p>
            <p className="font-bold text-primary">+{activity.points}</p>
          </div>
        </div>
        {activity.status === "active" && !activity.my_participation_id && (
          <Button
            className="w-full"
            disabled={isFull || join.isPending}
            onClick={() => join.mutate()}
          >
            {isFull ? "Activity is full" : join.isPending ? "Joining…" : "Join this activity"}
          </Button>
        )}
        {activity.my_participation_id && (
          <p className="rounded-lg bg-accent px-3 py-2 text-center text-sm text-accent-foreground">
            You joined — track it under “My participation”.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function MyParticipations() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["csr", "mine"],
    queryFn: () => api.get<CSRParticipationOut[]>("/csr/me"),
  });
  const attachProof = useMutation({
    mutationFn: ({ id, attachmentId }: { id: number; attachmentId: number }) =>
      api.post(`/csr/participations/${id}/proof`, { attachment_id: attachmentId }),
    onSuccess: () => {
      toast.success("Proof submitted for review");
      void qc.invalidateQueries({ queryKey: ["csr"] });
    },
    onError: (e) => toast.error(e.message),
  });

  if (isLoading) return <Skeleton className="h-40" />;
  if (!data?.length) {
    return (
      <EmptyState
        icon={HeartHandshake}
        title="No participation yet"
        description="Join an active CSR activity from the Explore tab to get started."
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
                <p className="font-semibold">{p.activity_title}</p>
                <p className="text-xs text-muted-foreground">
                  Joined {formatDate(p.created_at)}
                  {p.points_earned != null && (
                    <span className="ml-2 font-semibold text-primary">
                      +{p.points_earned} pts earned
                    </span>
                  )}
                </p>
              </div>
              <StatusChip status={p.status} />
            </div>
            {p.approver_comment && (
              <p className="mt-2 rounded-md bg-muted px-3 py-2 text-xs">
                <span className="font-semibold">{p.approver?.full_name ?? "Approver"}:</span>{" "}
                {p.approver_comment}
                {p.decided_at && (
                  <span className="text-muted-foreground"> · {formatDateTime(p.decided_at)}</span>
                )}
              </p>
            )}
            {["joined", "resubmission_requested"].includes(p.status) && (
              <div className="mt-3 border-t pt-3">
                <FileUpload
                  context="proof"
                  onUploaded={(attachmentId) =>
                    attachProof.mutate({ id: p.id, attachmentId })
                  }
                />
              </div>
            )}
            {p.status === "submitted" && p.proof && (
              <p className="mt-2 text-xs text-muted-foreground">
                Proof “{p.proof.original_name}” submitted — awaiting your department head.
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function CSRPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<CSRActivityOut | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["csr", "list", page, status, q],
    queryFn: () =>
      api.get<Page<CSRActivityOut>>(
        `/csr/activities?page=${page}&size=${PAGE_SIZE}` +
          (status ? `&status=${status}` : "") +
          (q ? `&q=${encodeURIComponent(q)}` : ""),
      ),
  });

  return (
    <div>
      <PageHeader
        title="CSR Activities"
        description="Volunteer for social impact, upload proof and earn points."
      />
      <Tabs defaultValue="explore">
        <TabsList>
          <TabsTrigger value="explore">Explore</TabsTrigger>
          <TabsTrigger value="mine">My participation</TabsTrigger>
        </TabsList>
        <TabsContent value="explore">
          <div className="mb-4 flex flex-wrap gap-2">
            <Input
              placeholder="Search activities…"
              className="max-w-56"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
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
              <option value="completed">Completed</option>
            </Select>
          </div>
          {isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-44" />
              ))}
            </div>
          ) : !data?.items.length ? (
            <EmptyState
              icon={HeartHandshake}
              title="No activities found"
              description="Try a different search or check back soon."
            />
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {data.items.map((a) => (
                  <ActivityCard key={a.id} activity={a} onOpen={() => setSelected(a)} />
                ))}
              </div>
              <Pager page={page} size={PAGE_SIZE} total={data.total} onPage={setPage} />
            </>
          )}
        </TabsContent>
        <TabsContent value="mine">
          <MyParticipations />
        </TabsContent>
      </Tabs>
      <ActivityDialog activity={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
