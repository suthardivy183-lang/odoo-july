import { FileCheck2, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { uploadFile } from "@/lib/api";

const MAX_MB = 10;
const ACCEPT = ".jpg,.jpeg,.png,.pdf";

export function FileUpload({
  context,
  onUploaded,
}: {
  context: string;
  onUploaded: (attachmentId: number, name: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  async function handleFile(file: File) {
    if (file.size > MAX_MB * 1024 * 1024) {
      toast.error(`File exceeds the ${MAX_MB} MB limit`);
      return;
    }
    setBusy(true);
    try {
      const res = await uploadFile(file, context);
      setFileName(file.name);
      onUploaded(res.id, file.name);
      toast.success("Proof uploaded");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void handleFile(f);
          e.target.value = "";
        }}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
      >
        {fileName ? <FileCheck2 /> : <UploadCloud />}
        {busy ? "Uploading…" : fileName ? "Replace file" : "Upload proof"}
      </Button>
      <span className="text-xs text-muted-foreground">
        {fileName ?? `JPG, PNG or PDF · max ${MAX_MB} MB`}
      </span>
    </div>
  );
}
