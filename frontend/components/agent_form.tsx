"use client";

import { useEffect, useState } from "react";
import {
  Loader2,
  Send,
  X,
  Upload,
  Folder,
  CloudUpload,
  CheckCircle2,
} from "lucide-react";

import type {
  QuickAction,
  FormField,
} from "@/lib/quick_actions";
import {
  fetchUserDatasets,
  type DatasetSummary,
} from "@/lib/datasets";
import { useAuthStore } from "@/lib/store/auth";

// =========================
// Types exposés
// =========================

export type FormSubmitPayload = {
  datasetId: string | null;
  file: File | null;
  extraParams: Record<string, string | number>;
  humanSummary: string;
};

type AgentFormProps = {
  action: QuickAction;
  onSubmit: (payload: FormSubmitPayload) => void;
  onCancel: () => void;
};

type Tab = "upload" | "select";

// =========================
// Composant principal
// =========================

export function AgentForm({ action, onSubmit, onCancel }: AgentFormProps) {
  const token = useAuthStore((s) => s.token);

  const [tab, setTab] = useState<Tab>("upload");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [extraValues, setExtraValues] = useState<Record<string, string | number>>(
    () => buildInitialValues(action.fields),
  );

  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [datasetsError, setDatasetsError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setDatasetsLoading(false);
      return;
    }
    let cancelled = false;
    setDatasetsLoading(true);
    setDatasetsError(null);

    fetchUserDatasets(token)
      .then((list) => {
        if (cancelled) return;
        setDatasets(list.filter((d) => d.status === "ready"));
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setDatasetsError(
          e instanceof Error ? e.message : "Erreur de chargement",
        );
      })
      .finally(() => {
        if (!cancelled) setDatasetsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  function handleFileChosen(file: File | null) {
    setUploadFile(file);
  }

  function handleSubmit() {
    if (tab === "upload" && !uploadFile) {
      alert("Veuillez sélectionner un fichier à uploader.");
      return;
    }
    if (tab === "select" && !selectedDatasetId) {
      alert("Veuillez sélectionner un dataset.");
      return;
    }

    const datasetField = action.fields.find(
      (f) => f.kind === "dataset_or_upload",
    );
    if (!datasetField) return;

    const humanSummary = buildHumanSummary(
      action,
      tab,
      uploadFile,
      datasets.find((d) => d.id === selectedDatasetId),
      extraValues,
    );

    onSubmit({
      datasetId: tab === "select" ? selectedDatasetId : null,
      file: tab === "upload" ? uploadFile : null,
      extraParams: extraValues,
      humanSummary,
    });
  }

  return (
    <div className="self-start max-w-[85%] flex gap-3">
      <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-sm font-bold text-white flex-shrink-0 shadow-lg shadow-emerald-900/40">
        V
      </div>

      <div className="flex-1 px-5 py-4 rounded-2xl bg-card border border-border text-foreground flex flex-col gap-4">
        <div>
          <h3 className="text-base font-semibold text-foreground mb-1">
            {action.title}
          </h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {action.formSubtitle}
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-xs font-medium text-foreground">
            Fichier à analyser
            <span className="text-red-400 ml-0.5">*</span>
          </label>

          <div className="flex gap-1 p-0.5 bg-background rounded-lg">
            <button
              type="button"
              onClick={() => setTab("upload")}
              className={`flex-1 px-3 py-1.5 rounded-md text-xs flex items-center justify-center gap-1.5 transition ${
                tab === "upload"
                  ? "bg-card border border-emerald-500/40 text-emerald-400"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Upload className="w-3.5 h-3.5" />
              Uploader un fichier
            </button>
            <button
              type="button"
              onClick={() => setTab("select")}
              className={`flex-1 px-3 py-1.5 rounded-md text-xs flex items-center justify-center gap-1.5 transition ${
                tab === "select"
                  ? "bg-card border border-emerald-500/40 text-emerald-400"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Folder className="w-3.5 h-3.5" />
              Choisir parmi mes données
            </button>
          </div>

          {tab === "upload" ? (
            <UploadDropzone file={uploadFile} onChange={handleFileChosen} />
          ) : (
            <DatasetPicker
              datasets={datasets}
              loading={datasetsLoading}
              error={datasetsError}
              selectedId={selectedDatasetId}
              onSelect={setSelectedDatasetId}
              matchActionKey={action.matchActionKey}
            />
          )}
        </div>

        {action.fields
          .filter((f) => f.kind !== "dataset_or_upload")
          .map((field) => (
            <FieldRenderer
              key={field.name}
              field={field}
              value={extraValues[field.name]}
              onChange={(v) =>
                setExtraValues((s) => ({ ...s, [field.name]: v }))
              }
            />
          ))}

        <div className="flex items-center gap-3 pt-1">
          <button
            type="button"
            onClick={handleSubmit}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition"
          >
            <Send className="w-3.5 h-3.5" />
            Envoyer
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-muted-foreground hover:text-foreground text-sm transition"
          >
            <X className="w-3.5 h-3.5" />
            Annuler
          </button>
        </div>
      </div>
    </div>
  );
}

// =========================
// Sous-composant : drop zone upload
// =========================

function UploadDropzone({
  file,
  onChange,
}: {
  file: File | null;
  onChange: (f: File | null) => void;
}) {
  const [isDragging, setIsDragging] = useState(false);

  function onFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    onChange(f);
  }

  function onDrop(e: React.DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files?.[0] ?? null;
    if (f) onChange(f);
  }

  if (file) {
    return (
      <div className="flex items-center justify-between gap-3 p-3 rounded-lg bg-background border border-emerald-500/30">
        <div className="flex items-center gap-2 min-w-0">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <div className="min-w-0">
            <div className="text-xs text-foreground truncate">{file.name}</div>
            <div className="text-[10px] text-muted-foreground">
              {(file.size / 1024).toFixed(1)} Ko
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={() => onChange(null)}
          className="text-muted-foreground hover:text-foreground shrink-0"
          aria-label="Retirer le fichier"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={onDrop}
      className={`flex flex-col items-center justify-center gap-1 p-6 rounded-lg cursor-pointer transition border-2 border-dashed ${
        isDragging
          ? "border-emerald-500 bg-emerald-500/5"
          : "border-border bg-background hover:border-border"
      }`}
    >
      <CloudUpload className="w-7 h-7 text-emerald-500 mb-1" />
      <div className="text-xs text-foreground">
        Glissez votre fichier ici ou cliquez pour parcourir
      </div>
      <div className="text-[10px] text-muted-foreground">CSV ou Excel · max 100 Mo</div>
      <input
        type="file"
        accept=".csv,.xlsx,.xls"
        onChange={onFileInput}
        className="hidden"
      />
    </label>
  );
}

// =========================
// Sous-composant : picker de datasets existants
// =========================

function DatasetPicker({
  datasets,
  loading,
  error,
  selectedId,
  onSelect,
  matchActionKey,
}: {
  datasets: DatasetSummary[];
  loading: boolean;
  error: string | null;
  selectedId: string;
  onSelect: (id: string) => void;
  matchActionKey: string;
}) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground text-xs p-3">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        Chargement des datasets…
      </div>
    );
  }

  if (error) {
    return <p className="text-xs text-red-400 p-2">{error}</p>;
  }

  if (datasets.length === 0) {
    return (
      <p className="text-xs text-muted-foreground italic p-3">
        Aucun dataset disponible. Utilisez l&apos;onglet &quot;Uploader un fichier&quot;.
      </p>
    );
  }

  const sorted = [...datasets].sort((a, b) => {
    const aMatch = a.matches_for_action?.includes(matchActionKey) ? 0 : 1;
    const bMatch = b.matches_for_action?.includes(matchActionKey) ? 0 : 1;
    return aMatch - bMatch;
  });

  return (
    <div className="flex flex-col gap-1.5 max-h-56 overflow-y-auto pr-1">
      {sorted.map((d) => {
        const isSelected = d.id === selectedId;
        const isMatch = d.matches_for_action?.includes(matchActionKey);
        return (
          <button
            key={d.id}
            type="button"
            onClick={() => onSelect(d.id)}
            className={`text-left p-2.5 rounded-md border transition flex justify-between items-center gap-3 ${
              isSelected
                ? "border-emerald-500/40 bg-background"
                : "border-border bg-background hover:border-border"
            }`}
          >
            <div className="min-w-0 flex-1">
              <div className="text-xs text-foreground font-medium flex items-center gap-1.5">
                {isMatch && (
                  <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                )}
                <span className="truncate">{d.name}</span>
              </div>
              <div className="text-[10px] text-muted-foreground mt-0.5 truncate">
                {d.rows ?? "?"} lignes
                {d.domain && d.domain !== "Inconnu" ? ` · ${d.domain}` : ""}
                {isMatch ? " · adapté à cette analyse" : ""}
              </div>
            </div>
            <div
              className={`w-4 h-4 rounded-full border shrink-0 ${
                isSelected
                  ? "bg-emerald-500 border-emerald-500"
                  : "border-border"
              }`}
            >
              {isSelected && (
                <CheckCircle2 className="w-4 h-4 text-zinc-950" />
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}

// =========================
// Sous-composant : champ générique (select / text / number_select)
// =========================

function FieldRenderer({
  field,
  value,
  onChange,
}: {
  field: FormField;
  value: string | number | undefined;
  onChange: (v: string | number) => void;
}) {
  if (field.kind === "dataset_or_upload") return null;

  const optionalLabel = !field.required ? (
    <span className="text-muted-foreground font-normal"> (optionnel)</span>
  ) : null;

  if (field.kind === "select") {
    return (
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-foreground">
          {field.label}
          {optionalLabel}
        </label>
        <select
          value={(value as string) ?? field.default ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className="px-3 py-2 rounded-md bg-background border border-border text-foreground text-xs focus:border-emerald-500/60 focus:outline-none"
        >
          {field.options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  if (field.kind === "number_select") {
    return (
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-foreground">
          {field.label}
          {optionalLabel}
        </label>
        <select
          value={(value as number) ?? field.default ?? field.options[0]}
          onChange={(e) => onChange(Number(e.target.value))}
          className="px-3 py-2 rounded-md bg-background border border-border text-foreground text-xs focus:border-emerald-500/60 focus:outline-none"
        >
          {field.options.map((opt) => (
            <option key={opt} value={opt}>
              Top {opt}
            </option>
          ))}
        </select>
      </div>
    );
  }

  // field.kind === "text"
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-foreground">
        {field.label}
        {optionalLabel}
      </label>
      <input
        type="text"
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={field.placeholder ?? ""}
        className="px-3 py-2 rounded-md bg-background border border-border text-foreground text-xs placeholder:text-muted-foreground focus:border-emerald-500/60 focus:outline-none"
      />
    </div>
  );
}

// =========================
// Helpers
// =========================

function buildInitialValues(
  fields: FormField[],
): Record<string, string | number> {
  const v: Record<string, string | number> = {};
  for (const f of fields) {
    if (f.kind === "select" && f.default) v[f.name] = f.default;
    else if (f.kind === "number_select" && f.default !== undefined)
      v[f.name] = f.default;
    else if (f.kind === "text" && f.default) v[f.name] = f.default;
  }
  return v;
}

function buildHumanSummary(
  action: QuickAction,
  tab: Tab,
  uploadFile: File | null,
  selectedDataset: DatasetSummary | undefined,
  extraValues: Record<string, string | number>,
): string {
  const parts: string[] = [action.title];

  if (tab === "upload" && uploadFile) {
    parts.push(`fichier : ${uploadFile.name}`);
  } else if (tab === "select" && selectedDataset) {
    parts.push(selectedDataset.name);
  }

  for (const field of action.fields) {
    if (field.kind === "dataset_or_upload") continue;
    const v = extraValues[field.name];
    if (v === undefined || v === "" || v === null) continue;

    if (field.kind === "select") {
      const opt = field.options.find((o) => o.value === v);
      if (opt) parts.push(opt.label);
    } else if (field.kind === "number_select") {
      parts.push(`Top ${v}`);
    } else if (field.kind === "text") {
      parts.push(`${field.label}: ${v}`);
    }
  }

  return parts.join(" · ");
}