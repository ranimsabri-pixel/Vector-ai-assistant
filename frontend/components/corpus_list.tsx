"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  FolderOpen,
  Trash2,
  Pencil,
  MessageCircle,
  Plus,
} from "lucide-react";

import {
  listCorpora,
  deleteCorpus,
  fetchCorpus,
  type CorpusSummary,
  type CorpusDetail,
} from "@/lib/corpus";
import { useAuthStore } from "@/lib/store/auth";
import { useDiscussionsStore } from "@/lib/store/discussions";
import { useConfirm } from "@/lib/hooks/use-confirm";
import { DocumentListSkeleton } from "@/components/skeleton";
import { EmptyState } from "@/components/empty_state";
import { ConfirmDialog } from "@/components/confirm_dialog";
import { CorpusFormModal } from "@/components/corpus_form_modal";

export function CorpusList() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const addDiscussionWithCorpus = useDiscussionsStore((s) => s.addDiscussionWithCorpus);
  const { confirm, dialogProps } = useConfirm();

  const [corpora, setCorpora] = useState<CorpusSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [askingId, setAskingId] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingCorpus, setEditingCorpus] = useState<CorpusDetail | null>(null);

  const loadCorpora = useCallback(async () => {
    if (!token) return;
    try {
      const data = await listCorpora(token);
      setCorpora(data);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de chargement des corpus");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadCorpora();
  }, [loadCorpora]);

  function handleCreate() {
    setEditingCorpus(null);
    setModalOpen(true);
  }

  async function handleEdit(summary: CorpusSummary) {
    if (!token) return;
    try {
      const detail = await fetchCorpus(token, summary.id);
      setEditingCorpus(detail);
      setModalOpen(true);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de chargement du corpus");
    }
  }

  function handleSaved() {
    loadCorpora();
  }

  const handleAsk = useCallback(
    async (corpus: CorpusSummary) => {
      if (!token) return;
      setAskingId(corpus.id);
      try {
        await addDiscussionWithCorpus(token, corpus.id, corpus.name);
        router.push("/");
      } catch (e) {
        toast.error(
          e instanceof Error ? e.message : "Erreur de création de la conversation",
        );
      } finally {
        setAskingId(null);
      }
    },
    [token, addDiscussionWithCorpus, router],
  );

  const handleDelete = useCallback(
    async (corpus: CorpusSummary) => {
      if (!token) return;

      const ok = await confirm({
        title: "Supprimer ce corpus ?",
        description:
          `"${corpus.name}" sera supprime. Les ${corpus.document_count} document(s) qu'il contient ` +
          "resteront intacts dans l'onglet Documents.",
        confirmLabel: "Supprimer",
        variant: "danger",
      });

      if (!ok) return;

      setDeletingId(corpus.id);
      try {
        await deleteCorpus(token, corpus.id);
        setCorpora((prev) => prev.filter((c) => c.id !== corpus.id));
        toast.success("Corpus supprime");
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Erreur de suppression");
      } finally {
        setDeletingId(null);
      }
    },
    [token, confirm],
  );

  return (
    <>
      <button
        onClick={handleCreate}
        className="mb-4 flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm font-medium text-white transition-colors"
      >
        <Plus size={16} />
        Créer un corpus
      </button>

      {loading && corpora.length === 0 ? (
        <DocumentListSkeleton count={3} />
      ) : corpora.length === 0 ? (
        <EmptyState
          icon={FolderOpen}
          title="Aucun corpus pour le moment"
          description="Regroupe plusieurs documents dans un corpus pour interroger l'ensemble en une seule question."
        />
      ) : (
        <div className="space-y-2">
          {corpora.map((corpus) => {
            const isDeleting = deletingId === corpus.id;
            const isAsking = askingId === corpus.id;

            return (
              <div
                key={corpus.id}
                className="flex items-center gap-4 p-4 bg-card/50 border border-border rounded-xl hover:border-border hover:bg-card/70 transition-all duration-200"
              >
                <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center shrink-0">
                  <FolderOpen size={18} className="text-white" />
                </div>

                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground truncate mb-1">
                    {corpus.name}
                  </p>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-blue-950/60 text-blue-300">
                      {corpus.document_count} document{corpus.document_count > 1 ? "s" : ""}
                    </span>
                    {corpus.description && (
                      <span className="truncate max-w-xs">{corpus.description}</span>
                    )}
                    <span className="text-muted-foreground">
                      {new Date(corpus.created_at).toLocaleDateString("fr-FR", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => handleEdit(corpus)}
                    className="p-2 hover:bg-emerald-600/10 rounded-lg text-muted-foreground hover:text-emerald-400 transition-colors"
                    title="Voir / éditer"
                    aria-label="Voir ou éditer le corpus"
                  >
                    <Pencil size={15} />
                  </button>

                  <button
                    onClick={() => handleAsk(corpus)}
                    disabled={isAsking || corpus.document_count === 0}
                    className="p-2 hover:bg-emerald-600/10 rounded-lg text-muted-foreground hover:text-emerald-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    title={
                      corpus.document_count === 0
                        ? "Ajoute des documents avant d'interroger ce corpus"
                        : "Interroger ce corpus"
                    }
                    aria-label="Interroger ce corpus"
                  >
                    <MessageCircle size={15} />
                  </button>

                  <button
                    onClick={() => handleDelete(corpus)}
                    disabled={isDeleting}
                    className="p-2 hover:bg-red-600/10 rounded-lg text-muted-foreground hover:text-red-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    title="Supprimer définitivement"
                    aria-label="Supprimer"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <ConfirmDialog {...dialogProps} />
      <CorpusFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        corpus={editingCorpus}
        onSaved={handleSaved}
      />
    </>
  );
}
