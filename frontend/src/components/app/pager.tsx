import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";

export function Pager({
  page,
  size,
  total,
  onPage,
}: {
  page: number;
  size: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / size));
  if (pages <= 1) return null;
  return (
    <div className="mt-3 flex items-center justify-end gap-2 text-sm text-muted-foreground">
      <span>
        Page {page} of {pages} · {total} records
      </span>
      <Button variant="outline" size="icon" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        <ChevronLeft />
      </Button>
      <Button
        variant="outline"
        size="icon"
        disabled={page >= pages}
        onClick={() => onPage(page + 1)}
      >
        <ChevronRight />
      </Button>
    </div>
  );
}
