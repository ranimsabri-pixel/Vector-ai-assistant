"use client";

import { Loader2, X, CheckCircle2, AlertCircle } from "lucide-react";

import {
  getFileTypeColorClass,
  getFileTypeLabel,
  type DocumentStatus,
  type FileType,
} from "@/lib/documents";

type PdfAttachmentPillProps = {
  fileName: string;
  fileType: FileType;
  status: DocumentStatus;
  onRemove: () => void;
};

// Labels français par status
const STATUS_LABELS: Record<DocumentStatus, string> = {
  uploaded: "en attente…",
  parsing: "extraction du texte…",
  chunking: "découpage…",
  embedding: "indexation vectorielle…",
  ready: "prêt",
  error: "erreur",
};

export function PdfAttachmentPill({
  fileName,
  fileType,
  status,
  onRemove,
}: PdfAttachmentPillProps) {
  const isReady = status === "ready";
  const isError = status === "error";
  const isProcessing = !isReady && !isError;

  return (
    <div
      className={`inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border text-xs max-w-[240px] transition ${
        isReady
          ? "bg-emerald-950/40 border-emerald-800/60 text-emerald-100"
          : isError
          ? "bg-red-950/40 border-red-800/60 text-red-100"
          : "bg-amber-950/40 border-amber-800/60 text-amber-100"
      }`}
    >
      {/* Icône format (PDF/WORD) coloree */}
      <div
        className={`w-6 h-6 rounded flex items-center justify-center text-[7px] font-bold text-white shrink-0 ${getFileTypeColorClass(fileType)}`}
      >
        {getFileTypeLabel(fileType)}
      </div>

      {/* Nom fichier + status */}
      <div className="flex flex-col min-w-0 flex-1">
        <span className="truncate font-medium text-[11px]">{fileName}</span>
        <span className="flex items-center gap-1 text-[10px] opacity-70">
          {isProcessing && (
            <Loader2 className="w-2.5 h-2.5 animate-spin" />
          )}
          {isReady && <CheckCircle2 className="w-2.5 h-2.5" />}
          {isError && <AlertCircle className="w-2.5 h-2.5" />}
          {STATUS_LABELS[status]}
        </span>
      </div>

      {/* Bouton retirer */}
      <button
        onClick={onRemove}
        className="text-current opacity-60 hover:opacity-100 transition shrink-0"
        aria-label="Retirer le PDF"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}