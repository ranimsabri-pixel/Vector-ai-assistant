"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileSpreadsheet, X, Loader2 } from "lucide-react";

import { useAuthStore } from "@/lib/store/auth";
import { type DatasetDetail } from "@/lib/datasets";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_SIZE = 100 * 1024 * 1024; // 100 MB
const ACCEPTED = {
  "text/csv": [".csv"],
  "application/vnd.ms-excel": [".xls"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
};

interface DropzoneUploadProps {
  onUploadComplete: (dataset: DatasetDetail) => void;
  onError: (message: string) => void;
}

export function DropzoneUpload({
  onUploadComplete,
  onError,
}: DropzoneUploadProps) {
  const token = useAuthStore((s) => s.token);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) {
      setFile(accepted[0]);
    }
  }, []);

  const {
    getRootProps,
    getInputProps,
    isDragActive,
    isDragReject,
    fileRejections,
  } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxSize: MAX_SIZE,
    multiple: false,
    disabled: uploading,
  });

  // Upload via XMLHttpRequest pour avoir la progression
  function handleUpload() {
    if (!file || !token) return;

    setUploading(true);
    setProgress(0);

    const formData = new FormData();
    formData.append("file", file);
    if (name) formData.append("name", name);
    if (description) formData.append("description", description);

    const xhr = new XMLHttpRequest();

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      setUploading(false);
      if (xhr.status >= 200 && xhr.status < 300) {
        const dataset = JSON.parse(xhr.responseText);
        onUploadComplete(dataset);
        setFile(null);
        setName("");
        setDescription("");
        setProgress(0);
      } else {
        let detail = `Erreur ${xhr.status}`;
        try {
          const data = JSON.parse(xhr.responseText);
          detail = data.detail || detail;
        } catch {
          // ignore
        }
        onError(detail);
      }
    };

    xhr.onerror = () => {
      setUploading(false);
      onError("Erreur réseau pendant l'upload");
    };

    xhr.open("POST", `${API_URL}/datasets/upload`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.send(formData);
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  }

  const rejection = fileRejections[0];
  const rejectionMessage = rejection
    ? rejection.errors[0]?.code === "file-too-large"
      ? "Fichier trop volumineux (max 100 MB)"
      : rejection.errors[0]?.code === "file-invalid-type"
      ? "Format non supporté (CSV, XLSX ou XLS uniquement)"
      : "Fichier refusé"
    : null;

  return (
    <div className="bg-card/50 rounded-xl p-6 border border-border mb-8">
      <div className="flex items-center gap-2 mb-5">
        <Upload size={18} className="text-emerald-400" />
        <h2 className="text-base font-semibold text-foreground">
          Nouveau dataset
        </h2>
      </div>

      {/* Zone de drop */}
      {!file ? (
        <div
          {...getRootProps()}
          className={
            "border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all " +
            (isDragReject
              ? "border-red-500/60 bg-red-500/5"
              : isDragActive
              ? "border-emerald-500/60 bg-emerald-500/5 scale-[1.01]"
              : "border-border hover:border-emerald-500/40 hover:bg-card/80")
          }
        >
          <input {...getInputProps()} />
          <div className="flex flex-col items-center gap-3">
            <div
              className={
                "p-3 rounded-full transition-colors " +
                (isDragActive
                  ? "bg-emerald-500/20 text-emerald-400"
                  : "bg-muted text-muted-foreground")
              }
            >
              <Upload size={28} />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">
                {isDragActive
                  ? isDragReject
                    ? "Format non accepté"
                    : "Lâche le fichier ici"
                  : "Glisse un fichier ici, ou clique pour parcourir"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                CSV, XLSX ou XLS — max 100 MB
              </p>
            </div>
          </div>
        </div>
      ) : (
        /* Fichier sélectionné */
        <div className="border border-border rounded-xl p-4 bg-background">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center flex-shrink-0">
              <FileSpreadsheet size={18} className="text-emerald-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">
                {file.name}
              </p>
              <p className="text-xs text-muted-foreground">{formatSize(file.size)}</p>
            </div>
            {!uploading && (
              <button
                onClick={() => setFile(null)}
                className="p-2 text-muted-foreground hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                title="Retirer"
              >
                <X size={16} />
              </button>
            )}
          </div>

          {/* Barre de progression */}
          {uploading && (
            <div className="mt-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-muted-foreground flex items-center gap-2">
                  <Loader2 size={12} className="animate-spin" />
                  Upload en cours...
                </span>
                <span className="text-xs text-emerald-400 font-medium">
                  {progress}%
                </span>
              </div>
              <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-200"
                  style={{ width: progress + "%" }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {rejectionMessage && (
        <div className="mt-3 p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg">
          {rejectionMessage}
        </div>
      )}

      {/* Champs nom + description (visibles seulement si fichier sélectionné) */}
      {file && !uploading && (
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
              Nom (optionnel)
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ex: Clients Welyne"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
              Description (optionnel)
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Quelques mots pour décrire"
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
            />
          </div>
        </div>
      )}

      {/* Bouton Uploader */}
      {file && (
        <button
          onClick={handleUpload}
          disabled={uploading}
          className="mt-4 px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium text-sm text-white transition-colors"
        >
          {uploading ? "Upload en cours..." : "Uploader"}
        </button>
      )}
    </div>
  );
}