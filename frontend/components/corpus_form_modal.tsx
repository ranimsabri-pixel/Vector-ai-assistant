"use client";

import { useEffect, useMemo, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { toast } from "sonner";
import { Check, FileWarning, Loader2, Upload, X } from "lucide-react";

import { useAuthStore } from "@/lib/store/auth";
import {
  fetchUserDocuments,
  getFileTypeColorClass,
  getFileTypeFromName,
  getFileTypeLabel,
  pollDocumentReady,
  type DocumentSummary,
} from "@/lib/documents";
import {
  createCorpus,
  updateCorpus,
  addDocumentsToCorpus,
  removeDocumentsFromCorpus,
  uploadDocumentsToCorpus,
  fetchCorpus,
  type CorpusDetail,
} from "@/lib/corpus";

type CorpusFormModalProps = {
  open: boolean;
  onClose: () => void;
  corpus: CorpusDetail | null; // null = creation, sinon edition
  onSaved: (corpus: CorpusDetail) => void;
};

// Doit rester aligne avec ALLOWED_EXTENSIONS / MAX_FILE_SIZE cote backend
// (app/services/documents.py) -- validation client = confort, la vraie
// verification reste serveur.
const MAX_SIZE = 50 * 1024 * 1024; // 50 Mo
const MAX_FILES = 10;
const ACCEPTED = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
  "text/plain": [".txt"],
  "text/markdown": [".md"],
};

type StagedFile = {
  localId: string;
  file: File;
  clientError: string | null;
};

type UploadStatus = "uploading" | "ingesting" | "ready" | "error";

type UploadResult = {
  filename: string;
  documentId: string | null;
  status: UploadStatus;
  message: string | null;
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " o";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " Ko";
  return (bytes / 1024 / 1024).toFixed(1) + " Mo";
}

export function CorpusFormModal({
  open,
  onClose,
  corpus,
  onSaved,
}: CorpusFormModalProps) {
  const token = useAuthStore((s) => s.token);
  const isEditing = corpus !== null;

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [saving, setSaving] = useState(false);

  // Nouveaux fichiers a uploader directement (S5 J51)
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([]);
  const [uploadResults, setUploadResults] = useState<UploadResult[] | null>(null);

  // Reinitialise le formulaire a chaque ouverture (creation ou edition)
  useEffect(() => {
    if (!open) return;
    setName(corpus?.name ?? "");
    setDescription(corpus?.description ?? "");
    setSelectedIds(new Set(corpus?.documents.map((d) => d.id) ?? []));
    setTypeFilter("all");
    setStagedFiles([]);
    setUploadResults(null);

    if (!token) return;
    setLoadingDocs(true);
    fetchUserDocuments(token)
      .then((docs) => setDocuments(docs.filter((d) => d.status === "ready")))
      .catch((e) => {
        toast.error(e instanceof Error ? e.message : "Erreur de chargement des documents");
      })
      .finally(() => setLoadingDocs(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, corpus?.id, token]);

  const availableTypes = useMemo(
    () => Array.from(new Set(documents.map((d) => d.file_type))),
    [documents],
  );

  const filteredDocuments = useMemo(
    () =>
      typeFilter === "all"
        ? documents
        : documents.filter((d) => d.file_type === typeFilter),
    [documents, typeFilter],
  );

  function toggleDoc(docId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  }

  // ============================================================
  // Nouveaux fichiers — drag-and-drop (S5 J51)
  // ============================================================

  function onDrop(accepted: File[], rejected: FileRejection[]) {
    const total = stagedFiles.length + accepted.length + rejected.length;
    if (total > MAX_FILES) {
      toast.error(`Maximum ${MAX_FILES} fichiers par corpus en une fois`);
    }

    const newStaged: StagedFile[] = [
      ...accepted.map((file) => ({
        localId: `${file.name}-${file.size}-${crypto.randomUUID()}`,
        file,
        clientError: null,
      })),
      ...rejected.map(({ file, errors }) => ({
        localId: `${file.name}-${file.size}-${crypto.randomUUID()}`,
        file,
        clientError:
          errors[0]?.code === "file-too-large"
            ? "Trop volumineux (max 50 Mo)"
            : errors[0]?.code === "file-invalid-type"
            ? "Format non supporté"
            : "Fichier refusé",
      })),
    ];

    setStagedFiles((prev) => [...prev, ...newStaged].slice(0, MAX_FILES));
  }

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxSize: MAX_SIZE,
    multiple: true,
    disabled: saving || uploadResults !== null,
  });

  function removeStagedFile(localId: string) {
    setStagedFiles((prev) => prev.filter((f) => f.localId !== localId));
  }

  // ============================================================
  // Save
  // ============================================================

  const validStagedFiles = stagedFiles.filter((f) => !f.clientError);

  async function handleSave() {
    if (!token) return;
    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("Le nom du corpus est obligatoire");
      return;
    }

    setSaving(true);
    try {
      let savedCorpus: CorpusDetail;

      if (isEditing) {
        savedCorpus = await updateCorpus(token, corpus.id, {
          name: trimmedName,
          description: description.trim() || null,
        });

        const originalIds = new Set(corpus.documents.map((d) => d.id));
        const toAdd = [...selectedIds].filter((id) => !originalIds.has(id));
        const toRemove = [...originalIds].filter((id) => !selectedIds.has(id));

        if (toAdd.length > 0) {
          savedCorpus = await addDocumentsToCorpus(token, corpus.id, toAdd);
        }
        if (toRemove.length > 0) {
          savedCorpus = await removeDocumentsFromCorpus(token, corpus.id, toRemove);
        }
      } else {
        savedCorpus = await createCorpus(token, {
          name: trimmedName,
          description: description.trim() || null,
        });
        if (selectedIds.size > 0) {
          savedCorpus = await addDocumentsToCorpus(token, savedCorpus.id, [...selectedIds]);
        }
      }

      // Upload des nouveaux fichiers -- seulement possible une fois le
      // corpus garanti d'exister (id requis par l'endpoint).
      if (validStagedFiles.length > 0) {
        const batch = await uploadDocumentsToCorpus(
          token,
          savedCorpus.id,
          validStagedFiles.map((f) => f.file),
        );

        const results: UploadResult[] = [
          ...batch.uploaded.map((u) => ({
            filename: u.filename,
            documentId: u.document_id,
            status: "ingesting" as const,
            message: null,
          })),
          ...batch.errors.map((e) => ({
            filename: e.filename,
            documentId: null,
            status: "error" as const,
            message: e.error,
          })),
        ];
        setUploadResults(results);

        // Poll chaque document uploade jusqu'a ready/error, en tache de
        // fond -- la modale reste ouverte pour montrer la progression.
        for (const u of batch.uploaded) {
          pollDocumentReady(u.document_id, token)
            .then(() => {
              setUploadResults((prev) =>
                prev?.map((r) =>
                  r.documentId === u.document_id ? { ...r, status: "ready" } : r,
                ) ?? null,
              );
            })
            .catch((e) => {
              setUploadResults((prev) =>
                prev?.map((r) =>
                  r.documentId === u.document_id
                    ? { ...r, status: "error", message: e instanceof Error ? e.message : "Échec de l'ingestion" }
                    : r,
                ) ?? null,
              );
            });
        }

        savedCorpus = await fetchCorpus(token, savedCorpus.id);
      }

      toast.success(isEditing ? "Corpus mis a jour" : "Corpus cree");
      onSaved(savedCorpus);

      // Si des uploads sont en cours, on laisse la modale ouverte pour
      // que l'utilisateur voie leur progression (point de vigilance J51 :
      // ne pas fermer une modale avec un upload en cours).
      if (validStagedFiles.length === 0) {
        onClose();
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur d'enregistrement");
    } finally {
      setSaving(false);
    }
  }

  const stillIngesting = uploadResults?.some((r) => r.status === "ingesting") ?? false;

  function handleRequestClose() {
    if (saving) return; // upload/creation en cours, on bloque la fermeture
    onClose();
  }

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/60 z-40 animate-fade-in"
        onClick={handleRequestClose}
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="w-full max-w-lg bg-card border border-border rounded-2xl shadow-2xl animate-message-in pointer-events-auto overflow-hidden flex flex-col max-h-[85vh]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-5 border-b border-border shrink-0">
            <h2 className="text-base font-semibold text-foreground">
              {isEditing ? "Modifier le corpus" : "Créer un corpus"}
            </h2>
            <button
              onClick={handleRequestClose}
              disabled={saving}
              className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
              aria-label="Fermer"
            >
              <X size={16} />
            </button>
          </div>

          <div className="p-5 space-y-4 overflow-y-auto">
            {uploadResults === null && (
              <>
                <div>
                  <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                    Nom
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Ex: Rapports Deloitte 2026"
                    autoFocus
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                    Description (optionnel)
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="À quoi sert ce corpus ?"
                    rows={2}
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60 resize-none transition-colors"
                  />
                </div>

                {/* Uploader de nouveaux documents (S5 J51) */}
                <div>
                  <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                    Uploader de nouveaux documents
                  </label>
                  <div
                    {...getRootProps()}
                    data-testid="corpus-dropzone"
                    className={
                      "border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-all " +
                      (isDragReject
                        ? "border-red-500/60 bg-red-500/5"
                        : isDragActive
                        ? "border-emerald-500/60 bg-emerald-500/5"
                        : "border-border hover:border-emerald-500/40 hover:bg-background")
                    }
                  >
                    <input {...getInputProps()} />
                    <div className="flex flex-col items-center gap-1.5">
                      <Upload size={18} className="text-muted-foreground" />
                      <p className="text-xs text-foreground">
                        {isDragActive
                          ? "Lâche les fichiers ici"
                          : "Glisse des fichiers ici, ou clique pour parcourir"}
                      </p>
                      <p className="text-[10px] text-muted-foreground">
                        PDF, DOCX, PPTX, TXT ou MD — max 50 Mo, {MAX_FILES} fichiers max
                      </p>
                    </div>
                  </div>

                  {stagedFiles.length > 0 && (
                    <div className="mt-2 border border-border rounded-lg divide-y divide-border max-h-40 overflow-y-auto">
                      {stagedFiles.map((sf) => {
                        const fileType = getFileTypeFromName(sf.file.name);
                        return (
                          <div
                            key={sf.localId}
                            className="flex items-center gap-2 px-3 py-2"
                          >
                            <span
                              className={`px-1.5 py-0.5 rounded text-[8px] font-bold text-white shrink-0 ${getFileTypeColorClass(fileType)}`}
                            >
                              {getFileTypeLabel(fileType)}
                            </span>
                            <span className="text-xs text-foreground truncate flex-1">
                              {sf.file.name}
                            </span>
                            <span className="text-[10px] text-muted-foreground shrink-0">
                              {formatSize(sf.file.size)}
                            </span>
                            {sf.clientError ? (
                              <span
                                className="text-red-400 shrink-0"
                                title={sf.clientError}
                              >
                                <FileWarning size={14} />
                              </span>
                            ) : null}
                            <button
                              type="button"
                              onClick={() => removeStagedFile(sf.localId)}
                              className="p-1 text-muted-foreground hover:text-red-400 rounded transition-colors shrink-0"
                              title="Retirer"
                            >
                              <X size={12} />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold">
                      Documents existants
                    </label>
                    <span className="text-[11px] text-emerald-400 font-medium">
                      {selectedIds.size} document{selectedIds.size > 1 ? "s" : ""} selectionne
                      {selectedIds.size > 1 ? "s" : ""}
                    </span>
                  </div>

                  {availableTypes.length > 1 && (
                    <div className="flex items-center gap-1.5 mb-2">
                      <button
                        onClick={() => setTypeFilter("all")}
                        className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                          typeFilter === "all"
                            ? "bg-emerald-600/20 text-emerald-400 border border-emerald-600/40"
                            : "bg-background text-muted-foreground border border-border hover:text-foreground"
                        }`}
                      >
                        Tous
                      </button>
                      {availableTypes.map((t) => (
                        <button
                          key={t}
                          onClick={() => setTypeFilter(t)}
                          className={`px-2 py-1 rounded text-[11px] font-medium transition-colors ${
                            typeFilter === t
                              ? "bg-emerald-600/20 text-emerald-400 border border-emerald-600/40"
                              : "bg-background text-muted-foreground border border-border hover:text-foreground"
                          }`}
                        >
                          {getFileTypeLabel(t)}
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="border border-border rounded-lg max-h-56 overflow-y-auto">
                    {loadingDocs ? (
                      <div className="flex items-center justify-center gap-2 py-6 text-xs text-muted-foreground">
                        <Loader2 size={14} className="animate-spin" />
                        Chargement des documents...
                      </div>
                    ) : filteredDocuments.length === 0 ? (
                      <p className="text-xs text-muted-foreground text-center py-6 italic">
                        Aucun document pret disponible
                      </p>
                    ) : (
                      <div className="divide-y divide-border">
                        {filteredDocuments.map((doc) => {
                          const checked = selectedIds.has(doc.id);
                          return (
                            <button
                              key={doc.id}
                              type="button"
                              onClick={() => toggleDoc(doc.id)}
                              className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-muted/50 transition-colors text-left"
                            >
                              <div
                                className={`w-4 h-4 rounded flex items-center justify-center shrink-0 border transition-colors ${
                                  checked
                                    ? "bg-emerald-600 border-emerald-600"
                                    : "border-border"
                                }`}
                              >
                                {checked && <Check size={11} className="text-white" />}
                              </div>
                              <span className="text-xs text-foreground truncate flex-1">
                                {doc.name}
                              </span>
                              <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold shrink-0">
                                {getFileTypeLabel(doc.file_type)}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* Recap post-upload (S5 J51) : statut d'ingestion en temps reel */}
            {uploadResults !== null && (
              <div>
                <p className="text-xs text-muted-foreground mb-2">
                  {uploadResults.filter((r) => r.status !== "error").length} document(s)
                  créé(s)
                  {uploadResults.some((r) => r.status === "error") &&
                    ` · ${uploadResults.filter((r) => r.status === "error").length} erreur(s)`}
                </p>
                <div className="border border-border rounded-lg divide-y divide-border">
                  {uploadResults.map((r) => (
                    <div key={r.filename} className="flex items-center gap-2.5 px-3 py-2">
                      {r.status === "ingesting" && (
                        <Loader2 size={14} className="animate-spin text-muted-foreground shrink-0" />
                      )}
                      {r.status === "ready" && (
                        <Check size={14} className="text-emerald-500 shrink-0" />
                      )}
                      {r.status === "error" && (
                        <span title={r.message ?? "Erreur"}>
                          <FileWarning size={14} className="text-red-400 shrink-0" />
                        </span>
                      )}
                      <span className="text-xs text-foreground truncate flex-1">
                        {r.filename}
                      </span>
                      <span className="text-[10px] text-muted-foreground shrink-0">
                        {r.status === "ingesting" && "Ingestion..."}
                        {r.status === "ready" && "Prêt"}
                        {r.status === "error" && "Erreur"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="flex gap-2 p-4 bg-background/50 border-t border-border shrink-0">
            {uploadResults === null ? (
              <>
                <button
                  onClick={handleRequestClose}
                  disabled={saving}
                  className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors disabled:opacity-40"
                >
                  Annuler
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving || !name.trim()}
                  className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {saving && <Loader2 size={14} className="animate-spin" />}
                  {saving ? "Enregistrement..." : "Enregistrer"}
                </button>
              </>
            ) : (
              <button
                data-testid="corpus-upload-recap-close"
                onClick={onClose}
                title={
                  stillIngesting
                    ? "L'ingestion continue en arrière-plan après fermeture"
                    : undefined
                }
                className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 transition-colors"
              >
                {stillIngesting ? "Fermer (ingestion en arrière-plan)" : "Fermer"}
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
