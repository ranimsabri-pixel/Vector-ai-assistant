"use client";

import { useEffect, useState, useMemo } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { ChevronLeft, ChevronRight, X, Loader2, AlertCircle } from "lucide-react";

import { useAuthStore } from "@/lib/store/auth";
import { usePdfViewerStore } from "@/lib/hooks/use-pdf-viewer";

// ============================================================
// Configuration worker PDF.js (via CDN, version matchée automatiquement)
// ============================================================
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

// Styles CSS de react-pdf (nécessaires pour le rendu)
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function PdfViewerPanel() {
  const token = useAuthStore((s) => s.token);
  const {
    isOpen,
    documentId,
    fileName,
    currentPage,
    totalPages,
    closeViewer,
    setCurrentPage,
    setTotalPages,
  } = usePdfViewerStore();

  const [pdfBlob, setPdfBlob] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // ============================================================
  // Fetch le PDF en Blob URL (le token va dans le header, pas dans l'URL)
  // ============================================================
  useEffect(() => {
    if (!isOpen || !documentId || !token) {
      setPdfBlob(null);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;

    async function loadPdf() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const res = await fetch(
          `${API_BASE_URL}/documents/${documentId}/download`,
          {
            headers: { Authorization: `Bearer ${token}` },
          },
        );

        if (!res.ok) {
          throw new Error(`Erreur ${res.status} : téléchargement PDF échoué`);
        }

        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);

        if (!cancelled) {
          setPdfBlob(objectUrl);
        }
      } catch (e) {
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : "Erreur inconnue");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    loadPdf();

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [isOpen, documentId, token]);

  // Options mémoïsées pour éviter le re-render intempestif du Document
  const documentOptions = useMemo(
    () => ({
      cMapUrl: `//unpkg.com/pdfjs-dist@${pdfjs.version}/cmaps/`,
      cMapPacked: true,
    }),
    [],
  );

  if (!isOpen) return null;

  const canPrev = currentPage > 1;
  const canNext = currentPage < totalPages;

  return (
    <aside className="h-full bg-background border-l border-border flex flex-col overflow-hidden animate-slide-in-right">
      {/* Header avec nom + navigation + close */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-background shrink-0">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <div className="w-6 h-6 rounded bg-emerald-600 flex items-center justify-center text-[9px] font-bold text-white shrink-0">
            PDF
          </div>
          <span className="text-sm font-medium text-foreground truncate">
            {fileName || "Document"}
          </span>
        </div>

        <button
          onClick={closeViewer}
          className="ml-2 p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground transition-colors shrink-0"
          aria-label="Fermer le viewer PDF"
        >
          <X size={16} />
        </button>
      </div>

      {/* Body : le PDF */}
      <div className="flex-1 overflow-auto bg-card/40 flex justify-center py-6 px-2">
        {isLoading && (
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            Chargement du PDF…
          </div>
        )}

        {loadError && (
          <div className="flex items-start gap-2 text-red-400 text-sm max-w-md px-4">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{loadError}</span>
          </div>
        )}

        {pdfBlob && !isLoading && (
          <Document
            file={pdfBlob}
            options={documentOptions}
            onLoadSuccess={({ numPages }) => setTotalPages(numPages)}
            onLoadError={(err) => setLoadError(err.message)}
            loading={
              <div className="text-muted-foreground text-sm">Analyse du PDF…</div>
            }
          >
            <Page
              pageNumber={currentPage}
              width={480}
              className="shadow-2xl"
              renderTextLayer={false}
              renderAnnotationLayer={false}
            />
          </Document>
        )}
      </div>

      {/* Footer : navigation pages */}
      {pdfBlob && totalPages > 0 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-background shrink-0">
          <button
            onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
            disabled={!canPrev}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-card hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed text-sm text-foreground transition-colors"
          >
            <ChevronLeft size={14} />
            Préc.
          </button>

          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="number"
              min={1}
              max={totalPages}
              value={currentPage}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val) && val >= 1 && val <= totalPages) {
                  setCurrentPage(val);
                }
              }}
              className="w-14 px-2 py-1 bg-card border border-border rounded text-center text-foreground focus:outline-none focus:border-emerald-500/60"
            />
            <span>/ {totalPages}</span>
          </div>

          <button
            onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
            disabled={!canNext}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-card hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed text-sm text-foreground transition-colors"
          >
            Suiv.
            <ChevronRight size={14} />
          </button>
        </div>
      )}
    </aside>
  );
}