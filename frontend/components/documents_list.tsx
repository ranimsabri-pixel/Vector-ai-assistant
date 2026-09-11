"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  FileText,
  Trash2,
  Eye,
  MessageCircle,
  Loader2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";

import {
  fetchUserDocuments,
  deleteDocument,
  downloadDocument,
  reingestDocument,
  getFileTypeLabel,
  getFileTypeColorClass,
  type DocumentSummary,
  type DocumentStatus,
} from "@/lib/documents";
import { useAuthStore } from "@/lib/store/auth";
import { usePdfViewerStore } from "@/lib/hooks/use-pdf-viewer";
import { useDiscussionsStore } from "@/lib/store/discussions";
import { useConfirm } from "@/lib/hooks/use-confirm";
import { DocumentListSkeleton } from "@/components/skeleton";
import { EmptyState } from "@/components/empty_state";
import { ConfirmDialog } from "@/components/confirm_dialog";

const STATUS_CONFIG: Record<
  DocumentStatus,
  { label: string; bgClass: string; textClass: string; iconBgClass: string }
> = {
  uploaded: {
    label: "En attente",
    bgClass: "bg-card",
    textClass: "text-muted-foreground",
    iconBgClass: "bg-muted",
  },
  parsing: {
    label: "Extraction...",
    bgClass: "bg-amber-950/60",
    textClass: "text-amber-300",
    iconBgClass: "bg-amber-600",
  },
  chunking: {
    label: "Decoupage...",
    bgClass: "bg-amber-950/60",
    textClass: "text-amber-300",
    iconBgClass: "bg-amber-600",
  },
  embedding: {
    label: "Indexation...",
    bgClass: "bg-amber-950/60",
    textClass: "text-amber-300",
    iconBgClass: "bg-amber-600",
  },
  ready: {
    label: "Pret",
    bgClass: "bg-emerald-950/60",
    textClass: "text-emerald-300",
    iconBgClass: "bg-emerald-600",
  },
  error: {
    label: "Erreur",
    bgClass: "bg-red-950/60",
    textClass: "text-red-300",
    iconBgClass: "bg-red-600",
  },
};

export function DocumentsList() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const openViewer = usePdfViewerStore((s) => s.openViewer);
  const addDiscussionWithDoc = useDiscussionsStore((s) => s.addDiscussionWithDoc);
  const { confirm, dialogProps } = useConfirm();

  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [reingestingId, setReingestingId] = useState<string | null>(null);

  const loadDocs = useCallback(async () => {
    if (!token) return;
    try {
      const docs = await fetchUserDocuments(token);
      setDocuments(docs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadDocs();
    const interval = setInterval(loadDocs, 5000);
    return () => clearInterval(interval);
  }, [loadDocs]);

  const handleView = useCallback(
    async (doc: DocumentSummary) => {
      if (doc.file_type === "pdf") {
        openViewer(doc.id, doc.original_filename, 1);
        return;
      }

      if (!token) return;
      try {
        await downloadDocument(token, doc.id, doc.original_filename);
        toast.info(`Téléchargement du fichier ${getFileTypeLabel(doc.file_type)}`);
      } catch (e) {
        toast.error(
          e instanceof Error ? e.message : "Erreur de téléchargement",
        );
      }
    },
    [openViewer, token],
  );

  const handleAsk = useCallback(
    async (doc: DocumentSummary) => {
      if (!token) return;
      try {
        await addDiscussionWithDoc(token, doc.id, doc.original_filename);
        router.push("/");
      } catch (e) {
        toast.error(
          e instanceof Error ? e.message : "Erreur de création de la conversation",
        );
      }
    },
    [token, addDiscussionWithDoc, router],
  );

  const handleDelete = useCallback(
    async (doc: DocumentSummary) => {
      if (!token) return;

      const ok = await confirm({
        title: "Supprimer le document ?",
        description:
          "Ce document et tous ses passages indexés seront supprimés définitivement. " +
          "Les conversations liées à ce document seront conservées mais ne pourront plus l'interroger.",
        confirmLabel: "Supprimer",
        variant: "danger",
      });

      if (!ok) return;

      setDeletingId(doc.id);
      try {
        await deleteDocument(token, doc.id);
        setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
        toast.success("Document supprime");
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Erreur de suppression");
      } finally {
        setDeletingId(null);
      }
    },
    [token, confirm],
  );

  const handleReingest = useCallback(
    async (doc: DocumentSummary) => {
      if (!token) return;

      setReingestingId(doc.id);
      try {
        const updated = await reingestDocument(token, doc.id);
        setDocuments((prev) =>
          prev.map((d) => (d.id === doc.id ? { ...d, ...updated } : d)),
        );
        toast.info("Re-ingestion en cours...");
        loadDocs();
      } catch (e) {
        toast.error(
          e instanceof Error ? e.message : "Erreur de re-ingestion",
        );
      } finally {
        setReingestingId(null);
      }
    },
    [token, loadDocs],
  );

  if (loading && documents.length === 0) {
    return <DocumentListSkeleton count={3} />;
  }

  if (error && documents.length === 0) {
    return (
      <div className="flex items-start gap-3 py-12 px-6 rounded-xl bg-red-950/30 border border-red-900/60 text-red-300 text-sm">
        <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-medium mb-1">Erreur de chargement</p>
          <p className="text-red-200/80 text-xs">{error}</p>
        </div>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title="Aucun document pour le moment"
        description="Vector peut lire et analyser vos PDFs. Joignez un document depuis le chat et posez-lui des questions."
      />
    );
  }

  return (
    <>
      <div className="space-y-2">
        {documents.map((doc) => {
          const config = STATUS_CONFIG[doc.status];
          const isReady = doc.status === "ready";
          const isProcessing = ["parsing", "chunking", "embedding"].includes(doc.status);
          const isDeleting = deletingId === doc.id;

          return (
            <div
              key={doc.id}
              className="flex items-center gap-4 p-4 bg-card/50 border border-border rounded-xl hover:border-border hover:bg-card/70 transition-all duration-200"
            >
              <div
                className={"w-10 h-10 rounded-lg " + getFileTypeColorClass(doc.file_type) + " flex items-center justify-center text-[10px] font-bold text-white shrink-0"}
              >
                {getFileTypeLabel(doc.file_type)}
              </div>

              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground truncate mb-1">
                  {doc.name}
                </p>
                <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                  <span
                    className={"inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium " + config.bgClass + " " + config.textClass}
                  >
                    {isProcessing && <Loader2 className="w-2.5 h-2.5 animate-spin" />}
                    {config.label}
                  </span>
                  {doc.page_count !== null && <span>{doc.page_count} pages</span>}
                  <span>{doc.chunk_count} chunks</span>
                  <span className="text-muted-foreground">
                    {new Date(doc.created_at).toLocaleDateString("fr-FR", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    })}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => handleView(doc)}
                  disabled={!isReady}
                  className="p-2 hover:bg-emerald-600/10 rounded-lg text-muted-foreground hover:text-emerald-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  title={
                    !isReady
                      ? "Ingestion en cours"
                      : doc.file_type === "pdf"
                      ? "Ouvrir dans le viewer"
                      : "Télécharger le document"
                  }
                  aria-label={
                    doc.file_type === "pdf"
                      ? "Ouvrir le viewer PDF"
                      : `Télécharger le document ${getFileTypeLabel(doc.file_type)}`
                  }
                >
                  <Eye size={15} />
                </button>

                <button
                  onClick={() => handleAsk(doc)}
                  disabled={!isReady}
                  className="p-2 hover:bg-emerald-600/10 rounded-lg text-muted-foreground hover:text-emerald-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  title={isReady ? "Poser une question sur ce document" : "Ingestion en cours"}
                  aria-label="Poser une question"
                >
                  <MessageCircle size={15} />
                </button>

                {isReady && (
                  <button
                    onClick={() => handleReingest(doc)}
                    disabled={reingestingId === doc.id}
                    className="p-2 hover:bg-emerald-600/10 rounded-lg text-muted-foreground hover:text-emerald-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    title="Ré-ingérer (relance l'extraction et l'indexation)"
                    aria-label="Ré-ingérer le document"
                  >
                    <RefreshCw
                      size={15}
                      className={reingestingId === doc.id ? "animate-spin" : ""}
                    />
                  </button>
                )}

                <button
                  onClick={() => handleDelete(doc)}
                  disabled={isProcessing || isDeleting}
                  className="p-2 hover:bg-red-600/10 rounded-lg text-muted-foreground hover:text-red-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  title={isProcessing ? "Ingestion en cours" : "Supprimer définitivement"}
                  aria-label="Supprimer"
                >
                  {isDeleting ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Trash2 size={15} />
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <ConfirmDialog {...dialogProps} />
    </>
  );
}