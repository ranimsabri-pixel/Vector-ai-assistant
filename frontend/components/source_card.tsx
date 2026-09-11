"use client";

import { FileText, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { usePdfViewerStore } from "@/lib/hooks/use-pdf-viewer";
import { useAuthStore } from "@/lib/store/auth";
import {
  downloadDocument,
  getFileTypeLabel,
  getFileTypeColorClass,
} from "@/lib/documents";
import type { RagSource } from "@/lib/rag";

type SourceCardProps = {
  source: RagSource;
  index: number;
  fileName?: string;
  onClick?: (source: RagSource) => void;
};

export function SourceCard({ source, index, fileName, onClick }: SourceCardProps) {

  const openViewer = usePdfViewerStore((s) => s.openViewer);
  const token = useAuthStore((s) => s.token);

  const fileType = source.document_file_type || "pdf";
  const isPdf = fileType === "pdf";
  const colorClass = getFileTypeColorClass(fileType);
  const accentTextClass =
    isPdf ? "text-emerald-400"
    : fileType === "docx" ? "text-blue-400"
    : fileType === "pptx" ? "text-orange-400"
    : fileType === "md" ? "text-violet-400"
    : "text-muted-foreground";

  const pageLabel =
    source.page_number === null
      ? "extrait"
      : fileType === "docx"
      ? `section ${source.page_number}`
      : fileType === "pptx"
      ? `slide ${source.page_number}`
      : fileType === "txt" || fileType === "md"
      ? `bloc ${source.page_number}`
      : `page ${source.page_number}`;

  // document_name vient du backend uniquement pour les reponses corpus
  // (multi-documents, J34) -- sinon on retombe sur la prop fileName.
  const displayName = source.document_name || fileName || null;

  const handleClick = async () => {
    if (onClick) {
      onClick(source);
      return;
    }

    // Word/PowerPoint : pas de viewer split-view, on telecharge directement
    if (!isPdf) {
      if (!token) return;
      try {
        await downloadDocument(token, source.document_id, displayName || `document.${fileType}`);
        toast.info(`Téléchargement du fichier ${getFileTypeLabel(fileType)}`);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Erreur de téléchargement");
      }
      return;
    }

    openViewer(
      source.document_id,
      displayName || "Document",
      source.page_number ?? 1,
    );
  };

  return (
    <button
      onClick={handleClick}
      className="group text-left px-3 py-2 rounded-lg bg-card/60 border border-border hover:border-emerald-700/60 hover:bg-card transition min-w-0 w-full"
    >
      <div className="flex items-start gap-2">
        <div
          className={`w-6 h-6 rounded flex items-center justify-center shrink-0 ${colorClass}`}
        >
          <FileText className="w-3 h-3 text-white" />
        </div>
        <div className="min-w-0 flex-1">
          {/* Nom du document — uniquement pour les sources corpus (multi-docs) */}
          {source.document_name && (
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="text-[11px] font-medium text-foreground truncate">
                {source.document_name}
              </span>
              <span
                className={`px-1 py-0.5 rounded text-[8px] font-bold text-white shrink-0 ${colorClass}`}
              >
                {getFileTypeLabel(fileType)}
              </span>
            </div>
          )}
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <span className={`text-[11px] font-semibold ${accentTextClass}`}>
              Source {index + 1} · {pageLabel}
            </span>
            <span className="text-[9px] text-muted-foreground font-mono shrink-0">
              {(source.similarity * 100).toFixed(0)}%
            </span>
          </div>
          <p className="text-[11px] text-muted-foreground leading-snug line-clamp-2">
            {source.content_preview}
          </p>
        </div>
        <ChevronRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-emerald-500 transition shrink-0 mt-0.5" />
      </div>
    </button>
  );
}