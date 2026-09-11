"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useConfirm } from "@/lib/hooks/use-confirm";
import { ConfirmDialog } from "@/components/confirm_dialog";
import {
  AlertTriangle,
  Loader2,
  Trash2,
  Upload,
  FileSpreadsheet,
  Sparkles,
} from "lucide-react";

import {
  uploadDataset,
  listDatasets,
  deleteDataset,
  profileDataset,
  type ColumnOverride,
  type Dataset,
} from "@/lib/datasets";
import {
  previewFile,
  FileTooLargeForPreviewError,
  type FilePreview,
} from "@/lib/file_preview";
import { useAuthStore } from "@/lib/store/auth";
import { Tabs, TabPanel } from "@/components/tabs";
import { DocumentsList } from "@/components/documents_list";
import { CorpusList } from "@/components/corpus_list";
import { DatasetListSkeleton } from "@/components/skeleton";
import { EmptyState } from "@/components/empty_state";
import {
  DatasetPreviewTable,
  type EditableColumnPreview,
} from "@/components/dataset_preview_table";

// Doit rester synchronise avec MAX_FILE_SIZE dans backend/app/services/datasets.py
const MAX_UPLOAD_FILE_SIZE = 100 * 1024 * 1024; // 100 Mo

export default function DatasetsPage() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const { confirm, dialogProps } = useConfirm();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [uploading, setUploading] = useState(false);
  const [profilingId, setProfilingId] = useState<string | null>(null);

  // Preview client-side (Phase 38.A/B/C)
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<FilePreview | null>(null);
  const [previewSkipped, setPreviewSkipped] = useState(false);
  const [editedColumns, setEditedColumns] = useState<EditableColumnPreview[] | null>(
    null,
  );

  const [activeTab, setActiveTab] = useState<"datasets" | "documents" | "corpus">(
    "datasets",
  );

  // ============================================================
  // Chargement des datasets
  // ============================================================

  useEffect(() => {
    if (token) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function refresh() {
    if (!token) return;
    setLoading(true);
    try {
      const data = await listDatasets(token);
      setDatasets(data);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }

  // ============================================================
  // Preview client-side du fichier (Phase 38.A/C)
  // ============================================================

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null;
    setFile(null);
    setPreview(null);
    setEditedColumns(null);
    setPreviewSkipped(false);
    if (!selected) return;

    if (selected.size > MAX_UPLOAD_FILE_SIZE) {
      toast.error(
        `Fichier trop volumineux (${(selected.size / 1024 / 1024).toFixed(1)} Mo). La taille maximale est de 100 Mo.`,
      );
      e.target.value = "";
      return;
    }

    setFile(selected);
    setPreviewing(true);
    try {
      const result = await previewFile(selected);
      setPreview(result);
    } catch (err) {
      if (err instanceof FileTooLargeForPreviewError) {
        setPreviewSkipped(true);
      } else {
        toast.error(
          err instanceof Error ? err.message : "Erreur d'aperçu du fichier",
        );
      }
    } finally {
      setPreviewing(false);
    }
  }

  // Ne remonte que les colonnes reellement modifiees par l'user (renommees,
  // retypees ou supprimees) -- tout ce qui n'est pas touche reste sous
  // l'autorite du profilage backend, qui reste la source de verite.
  function buildColumnOverrides(): ColumnOverride[] {
    if (!preview || !editedColumns) return [];
    const overrides: ColumnOverride[] = [];
    editedColumns.forEach((col, i) => {
      const original = preview.columns[i];
      if (!original) return;
      const renamed = col.name !== original.name;
      const retyped = col.detected_type !== original.detected_type;
      if (col.deleted || renamed || retyped) {
        overrides.push({
          original_name: col.original_name,
          new_name: renamed ? col.name : undefined,
          type: retyped ? col.detected_type : undefined,
          deleted: col.deleted || undefined,
        });
      }
    });
    return overrides;
  }

  // ============================================================
  // Upload d'un dataset
  // ============================================================

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !token) {
      toast.error("Sélectionne un fichier");
      return;
    }

    setUploading(true);

    try {
      const dataset = await uploadDataset(
        token,
        file,
        name || undefined,
        description || undefined,
        buildColumnOverrides(),
      );
      toast.success(`Dataset "${dataset.name}" uploadé avec succès`);

      // Lance le profilage tout de suite (applique les corrections
      // colonnes soumises ci-dessus). Non-bloquant : en cas d'echec,
      // le dataset reste "uploaded" et le bouton Reprofiler reste dispo.
      try {
        await profileDataset(token, dataset.id);
      } catch {
        toast.error("Upload réussi, mais le profilage automatique a échoué — réessaie via le bouton Reprofiler");
      }

      setFile(null);
      setName("");
      setDescription("");
      setPreview(null);
      setEditedColumns(null);
      setPreviewSkipped(false);
      const fileInput = document.getElementById(
        "dataset-file",
      ) as HTMLInputElement | null;
      if (fileInput) fileInput.value = "";
      await refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur d'upload");
    } finally {
      setUploading(false);
    }
  }

  // ============================================================
  // Delete d'un dataset
  // ============================================================

  async function handleDelete(id: string, datasetName: string) {
    if (!token) return;

    const ok = await confirm({
      title: `Supprimer "${datasetName}" ?`,
      description:
        "Ce dataset et toutes ses colonnes profilées seront supprimés définitivement. Cette action est irréversible.",
      confirmLabel: "Supprimer",
      variant: "danger",
    });

    if (!ok) return;

    try {
      await deleteDataset(token, id);
      toast.success(`Dataset "${datasetName}" supprimé`);
      await refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de suppression");
    }
  }

  // ============================================================
  // Profiler un dataset
  // ============================================================

  async function handleProfile(id: string) {
    if (!token) return;
    setProfilingId(id);

    try {
      await profileDataset(token, id);
      toast.success("Profilage lancé");
      await refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de profilage");
    } finally {
      setProfilingId(null);
    }
  }

  // ============================================================
  // Rendu
  // ============================================================

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="max-w-6xl mx-auto px-8 py-10">
        {/* ============================================================
            Titre — empreinte Vector : "Mes" blanc + "données" vert emerald
            ============================================================ */}
        <h1 className="text-4xl font-bold mb-2 tracking-tight">
          <span className="text-foreground">Mes </span>
          <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
            données
          </span>
        </h1>
        <p className="text-sm text-muted-foreground mb-8">
          Gère tes fichiers de données et documents joints aux conversations.
        </p>

        {/* ============================================================
            Barre d'onglets
            ============================================================ */}
        <Tabs
          tabs={[
            {
              id: "datasets",
              label: "Datasets",
              count: datasets.length,
            },
            {
              id: "documents",
              label: "Documents",
            },
            {
              id: "corpus",
              label: "Corpus",
            },
          ]}
          active={activeTab}
          onChange={setActiveTab}
        />

        {/* ============================================================
            Onglet DATASETS
            ============================================================ */}
        <TabPanel active={activeTab} value="datasets">
          {/* Formulaire d'upload */}
          <div className="bg-card/50 border border-border rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
              <Upload size={18} className="text-emerald-400" />
              Importer un nouveau dataset
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="dataset-file"
                  className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2"
                >
                  Fichier (CSV ou Excel)
                </label>
                <input
                  id="dataset-file"
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleFileChange}
                  className="w-full text-sm text-foreground file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-emerald-600/10 file:text-emerald-400 hover:file:bg-emerald-600/20 file:cursor-pointer cursor-pointer"
                />
              </div>

              <div>
                <label
                  htmlFor="dataset-name"
                  className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2"
                >
                  Nom (optionnel)
                </label>
                <input
                  id="dataset-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Nom du dataset"
                  className="w-full px-3 py-2 bg-card border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60"
                />
              </div>

              <div>
                <label
                  htmlFor="dataset-desc"
                  className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2"
                >
                  Description (optionnelle)
                </label>
                <textarea
                  id="dataset-desc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="À quoi sert ce dataset ?"
                  rows={2}
                  className="w-full px-3 py-2 bg-card border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60 resize-none"
                />
              </div>

              {previewing && (
                <div className="flex items-center justify-center gap-2 py-6 text-xs text-muted-foreground border border-border rounded-lg">
                  <Loader2 size={14} className="animate-spin" />
                  Analyse du fichier...
                </div>
              )}

              {previewSkipped && (
                <div className="flex items-start gap-2 py-3 px-3 text-xs text-amber-300 bg-amber-950/30 border border-amber-900/60 rounded-lg">
                  <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                  <span>
                    Fichier trop volumineux pour un aperçu (&gt;20 Mo). L&apos;upload
                    se fera directement, sans aperçu ni correction des colonnes.
                  </span>
                </div>
              )}

              {preview && !previewing && (
                <div>
                  <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                    Aperçu — corrige les colonnes si besoin
                  </label>
                  <DatasetPreviewTable
                    preview={preview}
                    editable
                    onColumnsChange={setEditedColumns}
                  />
                </div>
              )}

              <button
                type="submit"
                disabled={uploading || !file || previewing}
                className="w-full flex items-center justify-center gap-2 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white transition-colors"
              >
                <Upload size={16} />
                {uploading ? "Upload en cours..." : "Uploader et profiler"}
              </button>
            </form>
          </div>

          {/* Liste des datasets */}
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <FileSpreadsheet size={18} className="text-emerald-400" />
              Mes datasets ({datasets.length})
            </h2>
          </div>

          {loading && datasets.length === 0 ? (
            <DatasetListSkeleton count={3} />
          ) : datasets.length === 0 ? (
            <EmptyState
              icon={FileSpreadsheet}
              title="Prêt à explorer vos données"
              description="Importez votre premier fichier CSV ou Excel avec le formulaire ci-dessus. Vector analysera automatiquement les colonnes et vous permettra de générer des tableaux de bord."
            />
          ) : (
            <div className="space-y-2 pb-8">
              {datasets.map((ds) => (
                <div
                  key={ds.id}
                  className="flex items-center gap-4 p-4 bg-card/50 border border-border rounded-xl hover:border-border transition-colors"
                >
                  {/* Icône */}
                  <div className="w-10 h-10 rounded-lg bg-emerald-600 flex items-center justify-center shrink-0">
                    <FileSpreadsheet size={18} className="text-white" />
                  </div>

                  {/* Nom + métadonnées */}
                  <div
                    className="min-w-0 flex-1 cursor-pointer"
                    onClick={() => router.push(`/datasets/view?id=${ds.id}`)}
                  >
                    <p className="text-sm font-medium text-foreground truncate mb-0.5">
                      {ds.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {ds.status && (
                        <span
                          className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium mr-2 ${
                            ds.status === "ready"
                              ? "bg-emerald-950/60 text-emerald-300"
                              : ds.status === "profiling"
                              ? "bg-amber-950/60 text-amber-300"
                              : "bg-card text-muted-foreground"
                          }`}
                        >
                          {ds.status}
                        </span>
                      )}
                      {ds.row_count !== undefined &&
                        ds.row_count !== null && (
                          <span>{ds.row_count} lignes · </span>
                        )}
                      {ds.column_count !== undefined &&
                        ds.column_count !== null && (
                          <span>{ds.column_count} colonnes</span>
                        )}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => handleProfile(ds.id)}
                      disabled={profilingId === ds.id}
                      className="p-2 hover:bg-emerald-600/10 rounded-lg text-muted-foreground hover:text-emerald-400 transition-colors disabled:opacity-30"
                      title="Reprofiler"
                    >
                      <Sparkles size={15} />
                    </button>
                    <button
                      onClick={() => handleDelete(ds.id, ds.name)}
                      className="p-2 hover:bg-red-600/10 rounded-lg text-muted-foreground hover:text-red-400 transition-colors"
                      title="Supprimer"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabPanel>

        {/* ============================================================
            Onglet DOCUMENTS
            ============================================================ */}
        <TabPanel active={activeTab} value="documents">
          <div className="mb-6">
            <p className="text-sm text-muted-foreground">
              PDFs uploadés via le chat Vector. Pour en ajouter, utilise le
              bouton{" "}
              <span className="inline-flex items-center justify-center w-6 h-6 mx-0.5 bg-card border border-border rounded text-emerald-400 text-xs">
                📎
              </span>{" "}
              dans une conversation.
            </p>
          </div>
          <div className="pb-8">
            <DocumentsList />
          </div>
        </TabPanel>

        {/* ============================================================
            Onglet CORPUS (NEW J34)
            ============================================================ */}
        <TabPanel active={activeTab} value="corpus">
          <div className="mb-6">
            <p className="text-sm text-muted-foreground">
              Regroupe plusieurs documents (PDF, Word) dans un corpus pour
              interroger l&apos;ensemble en une seule question.
            </p>
          </div>
          <div className="pb-8">
            <CorpusList />
          </div>
        </TabPanel>
      </div>
      <ConfirmDialog {...dialogProps} />
    </div>
  );
}