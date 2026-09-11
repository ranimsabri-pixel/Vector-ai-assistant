"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Brain,
  CalendarDays,
  ChevronDown,
  ChevronUp,
  Download,
  Eye,
  Hash,
  LayoutDashboard,
  Pencil,
  Save,
  Sparkles,
  Tags,
  ToggleLeft,
  Trash2,
  Type,
  X,
} from "lucide-react";

import {
  analyzeDataset,
  downloadDatasetSample,
  getDataset,
  getDatasetColumns,
  profileDataset,
  pollDatasetStatus,
  reprofileDataset,
  updateDatasetColumns,
  type ColumnOverride,
  type DatasetColumn,
  type DatasetDetail,
} from "@/lib/datasets";
import { useAuthStore } from "@/lib/store/auth";
import { useToast } from "@/lib/hooks/use-toast";
import { ToastContainer } from "@/components/toast";
import { SemanticAnalysisCard } from "@/components/semantic-analysis-card";
import { ColumnStatsPanel } from "@/components/column_stats_panel";

type DtypeConfig = {
  label: string;
  color: string;
  icon: React.ComponentType<{ size?: number }>;
};

const DTYPE_CONFIG: Record<string, DtypeConfig> = {
  numeric: { label: "Numérique", color: "bg-blue-500/10 text-blue-400 border-blue-500/30", icon: Hash },
  categorical: { label: "Catégoriel", color: "bg-purple-500/10 text-purple-400 border-purple-500/30", icon: Tags },
  datetime: { label: "Date", color: "bg-amber-500/10 text-amber-400 border-amber-500/30", icon: CalendarDays },
  text: { label: "Texte", color: "bg-muted text-foreground border-border", icon: Type },
  boolean: { label: "Booléen", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30", icon: ToggleLeft },
};

const DTYPE_OPTIONS = ["numeric", "categorical", "datetime", "boolean", "text"];

type ColumnEdit = { new_name?: string; type?: string; deleted?: boolean };

export default function DatasetDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="h-full flex items-center justify-center">
          <p className="text-muted-foreground text-sm">Chargement...</p>
        </div>
      }
    >
      <DatasetDetailPageInner />
    </Suspense>
  );
}

function DatasetDetailPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const { toasts, success, error: toastError, removeToast } = useToast();
  const id = searchParams.get("id") ?? "";

  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [columns, setColumns] = useState<DatasetColumn[]>([]);
  const [loading, setLoading] = useState(true);
  const [profiling, setProfiling] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [edits, setEdits] = useState<Record<string, ColumnEdit>>({});
  const [savingEdits, setSavingEdits] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [reprofiling, setReprofiling] = useState(false);
  const [sampleMenuOpen, setSampleMenuOpen] = useState(false);
  const [exportingLimit, setExportingLimit] = useState<number | null>(null);

  useEffect(() => {
    if (!token || !id) return;
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id]);

  async function loadAll() {
    if (!token) return;
    setLoading(true);
    try {
      const [d, cols] = await Promise.all([
        getDataset(token, id),
        getDatasetColumns(token, id).catch(() => []),
      ]);
      setDataset(d);
      setColumns(cols);
    } catch (e) {
      toastError(e instanceof Error ? e.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }

  async function handleProfile() {
    if (!token) return;
    setProfiling(true);
    try {
      await profileDataset(token, id);
      success("Dataset profilé avec succès");
      await loadAll();
    } catch (e) {
      toastError(e instanceof Error ? e.message : "Erreur de profilage");
    } finally {
      setProfiling(false);
    }
  }

  async function handleAnalyze() {
    if (!token) return;
    setAnalyzing(true);
    try {
      await analyzeDataset(token, id);
      success("Analyse sémantique terminée");
      await loadAll();
    } catch (e) {
      toastError(e instanceof Error ? e.message : "Erreur d'analyse");
    } finally {
      setAnalyzing(false);
    }
  }

  function handleOpenDashboard() {
    window.open("/dashboard?id=" + id, "_blank");
  }

  function toggleExpanded(columnId: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(columnId)) next.delete(columnId);
      else next.add(columnId);
      return next;
    });
  }

  async function handleReprofile() {
    if (!token) return;
    setReprofiling(true);
    try {
      await reprofileDataset(token, id);
      await pollDatasetStatus(token, id, { intervalMs: 3000 });
      success("Dataset reprofilé avec succès");
      await loadAll();
    } catch (e) {
      toastError(e instanceof Error ? e.message : "Erreur de reprofilage");
    } finally {
      setReprofiling(false);
    }
  }

  async function handleSampleExport(limit: number) {
    if (!token || !dataset) return;
    setSampleMenuOpen(false);
    setExportingLimit(limit);
    try {
      await downloadDatasetSample(token, id, dataset.name, limit);
      success(`Échantillon de ${limit} lignes téléchargé`);
    } catch (e) {
      toastError(e instanceof Error ? e.message : "Erreur d'export");
    } finally {
      setExportingLimit(null);
    }
  }

  function setColumnEdit(columnName: string, patch: ColumnEdit) {
    setEdits((prev) => ({ ...prev, [columnName]: { ...prev[columnName], ...patch } }));
  }

  function toggleColumnDeleted(columnName: string) {
    setEdits((prev) => ({
      ...prev,
      [columnName]: { ...prev[columnName], deleted: !prev[columnName]?.deleted },
    }));
  }

  function handleCancelEdits() {
    setEdits({});
    setEditMode(false);
  }

  async function handleSaveEdits() {
    if (!token) return;

    const overrides: ColumnOverride[] = Object.entries(edits)
      .filter(
        ([, e]) => e.new_name !== undefined || e.type !== undefined || e.deleted !== undefined
      )
      .map(([original_name, e]) => ({
        original_name,
        ...(e.new_name && e.new_name !== original_name ? { new_name: e.new_name } : {}),
        ...(e.type ? { type: e.type } : {}),
        ...(e.deleted !== undefined ? { deleted: e.deleted } : {}),
      }));

    if (overrides.length === 0) {
      handleCancelEdits();
      return;
    }

    setSavingEdits(true);
    try {
      await updateDatasetColumns(token, id, overrides);
      await pollDatasetStatus(token, id, { intervalMs: 3000 });
      success("Colonnes mises à jour");
      setEdits({});
      setEditMode(false);
      await loadAll();
    } catch (e) {
      toastError(e instanceof Error ? e.message : "Erreur de mise à jour des colonnes");
    } finally {
      setSavingEdits(false);
    }
  }

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-muted-foreground text-sm">Chargement...</p>
      </div>
    );
  }

  if (!dataset) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-red-400 text-sm">Dataset introuvable</p>
      </div>
    );
  }

  const qualityPct = dataset.quality_score != null ? Math.round(dataset.quality_score * 100) : null;
  const issues = dataset.quality_issues || {};
  const completenessPct = (issues.completeness_pct as number | undefined) ?? null;
  const duplicateRows = (issues.duplicate_rows as number | undefined) ?? 0;
  const highNullCount = ((issues.high_null_columns as string[] | undefined) || []).length;
  const sample = dataset.raw_data_sample;
  const semantic = dataset.semantic_analysis;
  const isProfiled = dataset.status === "ready";
  const isAnalyzed = !!semantic;

  return (
    <>
      <ToastContainer toasts={toasts} onClose={removeToast} />

      <div className="h-full overflow-y-auto">
        <div className="max-w-6xl mx-auto px-8 py-10">
          <button
            onClick={() => router.push("/datasets")}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6 text-sm transition-colors"
          >
            <ArrowLeft size={16} />
            Retour aux datasets
          </button>

          {/* Header dataset */}
          <div className="bg-card/50 rounded-xl p-6 border border-border mb-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex-1 min-w-0">
                <h1 className="text-2xl font-bold text-foreground mb-2">{dataset.name}</h1>
                {dataset.description && (
                  <p className="text-muted-foreground text-sm mb-3">{dataset.description}</p>
                )}
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
                  <span>{dataset.original_filename}</span>
                  <span>{dataset.row_count?.toLocaleString("fr-FR")} lignes</span>
                  <span>{dataset.column_count} colonnes</span>
                  <span>Status : {dataset.status}</span>
                </div>
              </div>

              <div className="flex gap-2 flex-wrap">
                {!isProfiled && (
                  <button
                    onClick={handleProfile}
                    disabled={profiling}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white flex items-center gap-2 transition-colors"
                  >
                    <Sparkles size={16} className={profiling ? "animate-pulse" : ""} />
                    {profiling ? "Profilage..." : "Profiler"}
                  </button>
                )}
                {isProfiled && !isAnalyzed && (
                  <button
                    onClick={handleAnalyze}
                    disabled={analyzing}
                    className="px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white flex items-center gap-2 transition-colors shadow-lg shadow-purple-900/30"
                  >
                    <Brain size={16} className={analyzing ? "animate-pulse" : ""} />
                    {analyzing ? "Analyse..." : "Analyser avec Vector"}
                  </button>
                )}
                {isProfiled && (
                  <button
                    onClick={handleOpenDashboard}
                    className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 rounded-lg text-sm font-medium text-white flex items-center gap-2 transition-colors shadow-lg shadow-emerald-900/30"
                  >
                    <LayoutDashboard size={16} />
                    Ouvrir le dashboard
                  </button>
                )}
                {isProfiled && (
                  <div className="relative">
                    <button
                      onClick={() => setSampleMenuOpen((v) => !v)}
                      disabled={exportingLimit !== null}
                      className="px-4 py-2 bg-muted hover:bg-muted-foreground/10 disabled:opacity-40 rounded-lg text-sm font-medium text-foreground flex items-center gap-2 transition-colors"
                    >
                      <Download size={16} className={exportingLimit !== null ? "animate-pulse" : ""} />
                      {exportingLimit !== null ? `Export ${exportingLimit}...` : "Exporter un échantillon"}
                    </button>
                    {sampleMenuOpen && (
                      <>
                        <div
                          className="fixed inset-0 z-40"
                          onClick={() => setSampleMenuOpen(false)}
                        />
                        <div className="absolute z-50 top-full right-0 mt-1 w-40 bg-card border border-border rounded-lg shadow-2xl overflow-hidden">
                          {[100, 500, 1000].map((n) => (
                            <button
                              key={n}
                              onClick={() => handleSampleExport(n)}
                              className="w-full flex items-center px-3 py-2 text-xs text-foreground hover:bg-muted transition-colors text-left"
                            >
                              {n.toLocaleString("fr-FR")} lignes
                            </button>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )}
                {isProfiled && !editMode && (
                  <button
                    onClick={() => setEditMode(true)}
                    className="px-4 py-2 bg-muted hover:bg-muted-foreground/10 rounded-lg text-sm font-medium text-foreground flex items-center gap-2 transition-colors"
                  >
                    <Pencil size={16} />
                    Modifier les colonnes
                  </button>
                )}
                {editMode && (
                  <>
                    <button
                      onClick={handleCancelEdits}
                      disabled={savingEdits}
                      className="px-4 py-2 bg-muted hover:bg-muted-foreground/10 disabled:opacity-40 rounded-lg text-sm font-medium text-foreground flex items-center gap-2 transition-colors"
                    >
                      <X size={16} />
                      Annuler
                    </button>
                    <button
                      onClick={handleSaveEdits}
                      disabled={savingEdits}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white flex items-center gap-2 transition-colors"
                    >
                      <Save size={16} className={savingEdits ? "animate-pulse" : ""} />
                      {savingEdits ? "Enregistrement..." : "Enregistrer les corrections"}
                    </button>
                  </>
                )}
              </div>
            </div>

            {qualityPct != null && (
              <div className="mt-5 pt-5 border-t border-border grid grid-cols-2 md:grid-cols-4 gap-4">
                <Stat label="Qualité globale" value={qualityPct + "%"} accent={qualityPct >= 90 ? "emerald" : qualityPct >= 70 ? "amber" : "red"} />
                <Stat label="Complétude" value={(completenessPct ?? "?") + "%"} />
                <Stat label="Doublons" value={String(duplicateRows)} />
                <Stat label="Colonnes problématiques" value={String(highNullCount)} />
              </div>
            )}
          </div>

          {/* Analyse sémantique */}
          {semantic && <SemanticAnalysisCard analysis={semantic} />}

          {/* Aperçu tabulaire */}
          {sample && sample.columns && sample.rows && sample.rows.length > 0 && (
            <div className="bg-card/50 rounded-xl border border-border mb-6 overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-300">
              <div className="px-6 py-4 border-b border-border flex items-center gap-2">
                <Eye size={16} className="text-emerald-400" />
                <h2 className="text-sm font-semibold text-foreground">
                  Aperçu des 5 premières lignes
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-background/50">
                    <tr>
                      {sample.columns.map((col) => (
                        <th key={col} className="px-4 py-2 text-left text-xs uppercase tracking-wider text-muted-foreground font-semibold border-b border-border">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sample.rows.map((row, i) => (
                      <tr key={i} className="border-b border-border/50 hover:bg-card/30 transition-colors">
                        {row.map((cell, j) => (
                          <td key={j} className="px-4 py-2 text-foreground font-mono text-xs truncate max-w-[200px]" title={String(cell)}>
                            {String(cell) || (<span className="text-muted-foreground italic">vide</span>)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Liste des colonnes */}
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-4">
            Colonnes ({columns.length})
          </p>

          {columns.length === 0 ? (
            <div className="bg-card/30 rounded-xl p-12 text-center border border-dashed border-border">
              <Sparkles size={32} className="text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground text-sm">
                Pas encore profilé. Clique sur <strong>Profiler</strong> en haut.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {columns.map((col, i) => (
                <div key={col.id} style={{ animationDelay: i * 30 + "ms" }} className="animate-in fade-in slide-in-from-bottom-1 duration-300 fill-mode-both">
                  <ColumnCard
                    col={col}
                    totalRows={dataset.row_count}
                    editable={editMode}
                    edit={edits[col.name]}
                    onRename={(newName) => setColumnEdit(col.name, { new_name: newName })}
                    onTypeChange={(type) => setColumnEdit(col.name, { type })}
                    onToggleDeleted={() => toggleColumnDeleted(col.name)}
                    expanded={expandedIds.has(col.id)}
                    onToggleExpand={() => toggleExpanded(col.id)}
                    onReprofile={handleReprofile}
                    reprofiling={reprofiling}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function Stat(props: { label: string; value: string; accent?: "emerald" | "amber" | "red" }) {
  const colorClass =
    props.accent === "emerald" ? "text-emerald-400" :
    props.accent === "amber" ? "text-amber-400" :
    props.accent === "red" ? "text-red-400" :
    "text-foreground";

  return (
    <div>
      <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-1">{props.label}</p>
      <p className={"text-2xl font-bold " + colorClass}>{props.value}</p>
    </div>
  );
}

function ColumnCard(props: {
  col: DatasetColumn;
  totalRows: number | null;
  editable?: boolean;
  edit?: ColumnEdit;
  onRename?: (newName: string) => void;
  onTypeChange?: (type: string) => void;
  onToggleDeleted?: () => void;
  expanded?: boolean;
  onToggleExpand?: () => void;
  onReprofile?: () => void;
  reprofiling?: boolean;
}) {
  const col = props.col;
  const totalRows = props.totalRows;
  const editable = props.editable ?? false;
  const edit = props.edit;
  const isDeleted = !!edit?.deleted;
  const displayType = edit?.type || col.dtype || "text";
  const config = DTYPE_CONFIG[displayType] || DTYPE_CONFIG.text;
  const Icon = config.icon;
  const nullPct = totalRows && col.null_count != null ? Math.round((col.null_count / totalRows) * 100) : 0;
  const samples = (col.sample_values?.samples as unknown[]) || [];
  const stats = (col.sample_values?.stats as Record<string, unknown>) || {};
  const topValues = stats.top_values as Record<string, number> | undefined;
  const topEntries = topValues ? Object.entries(topValues).slice(0, 3) : [];

  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState(edit?.new_name ?? col.name);

  function commitRename() {
    setRenaming(false);
    const trimmed = nameDraft.trim();
    if (trimmed && props.onRename) props.onRename(trimmed);
  }

  return (
    <div
      className={
        "bg-card/50 border border-border rounded-xl p-4 hover:border-border transition-colors" +
        (isDeleted ? " opacity-50" : "")
      }
    >
      <div className="flex items-start gap-3 mb-3">
        <div className={"p-2 rounded-lg border flex-shrink-0 " + config.color}>
          <Icon size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            {editable && renaming ? (
              <input
                autoFocus
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                onBlur={commitRename}
                onKeyDown={(e) => {
                  if (e.key === "Enter") e.currentTarget.blur();
                  if (e.key === "Escape") setRenaming(false);
                }}
                className="px-1.5 py-0.5 bg-background border border-emerald-500/60 rounded text-sm text-foreground focus:outline-none"
              />
            ) : (
              <h3
                onClick={() => editable && !isDeleted && setRenaming(true)}
                className={
                  "font-semibold truncate " +
                  (isDeleted ? "line-through text-red-400" : "text-foreground") +
                  (editable && !isDeleted ? " cursor-pointer hover:text-emerald-400" : "")
                }
                title={editable ? "Cliquer pour renommer" : undefined}
              >
                {edit?.new_name || col.name}
              </h3>
            )}

            {editable && !isDeleted ? (
              <select
                value={displayType}
                onChange={(e) => props.onTypeChange?.(e.target.value)}
                className={"px-2 py-0.5 rounded text-xs font-medium border bg-background " + config.color}
              >
                {DTYPE_OPTIONS.map((t) => (
                  <option key={t} value={t}>
                    {DTYPE_CONFIG[t].label}
                  </option>
                ))}
              </select>
            ) : (
              <span className={"px-2 py-0.5 rounded text-xs font-medium border " + config.color}>
                {config.label}
              </span>
            )}

            {col.is_date_main && (
              <span className="px-2 py-0.5 rounded text-xs font-medium border bg-amber-500/10 text-amber-400 border-amber-500/30">
                Date principale
              </span>
            )}

            {editable && (
              <button
                onClick={props.onToggleDeleted}
                title={isDeleted ? "Restaurer la colonne" : "Supprimer cette colonne"}
                className={
                  "p-1.5 rounded transition-colors " +
                  (isDeleted
                    ? "text-muted-foreground hover:text-emerald-400 hover:bg-muted"
                    : "text-muted-foreground hover:text-red-400 hover:bg-red-950/40")
                }
              >
                <Trash2 size={14} />
              </button>
            )}
            <button
              onClick={props.onToggleExpand}
              title={props.expanded ? "Masquer les statistiques" : "Voir les statistiques détaillées"}
              className={"p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" + (editable ? "" : " ml-auto")}
            >
              {props.expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground mt-1">
            <span>{col.unique_count?.toLocaleString("fr-FR")} uniques</span>
            <span className={nullPct > 30 ? "text-red-400" : ""}>
              {nullPct}% nulls ({col.null_count?.toLocaleString("fr-FR")})
            </span>
          </div>
        </div>
      </div>

      {samples.length > 0 && (
        <div className="mb-2">
          <p className="text-xs text-muted-foreground mb-1">Échantillons :</p>
          <div className="flex flex-wrap gap-1.5">
            {samples.slice(0, 5).map((s, i) => (
              <span key={i} className="px-2 py-0.5 bg-background border border-border rounded text-xs text-foreground font-mono truncate max-w-[200px]">
                {String(s)}
              </span>
            ))}
          </div>
        </div>
      )}

      {col.dtype === "numeric" && stats.min !== undefined && (
        <div className="text-xs text-muted-foreground">
          min <span className="text-foreground">{String(stats.min)}</span> · max{" "}
          <span className="text-foreground">{String(stats.max)}</span> · moy{" "}
          <span className="text-foreground">{String(stats.mean)}</span>
        </div>
      )}

      {col.dtype === "datetime" && stats.min !== undefined && (
        <div className="text-xs text-muted-foreground">
          du <span className="text-foreground">{String(stats.min)}</span> au{" "}
          <span className="text-foreground">{String(stats.max)}</span> (
          <span className="text-foreground">{String(stats.span_days)}</span> jours)
        </div>
      )}

      {col.dtype === "categorical" && topEntries.length > 0 && (
        <div className="text-xs text-muted-foreground">
          Top :{" "}
          {topEntries.map(([k, v]) => (
            <span key={k} className="text-foreground mr-2">
              {k} ({v})
            </span>
          ))}
        </div>
      )}

      {col.dtype === "boolean" && stats.true_count !== undefined && (
        <div className="text-xs text-muted-foreground">
          true <span className="text-emerald-400">{String(stats.true_count)}</span> · false{" "}
          <span className="text-foreground">{String(stats.false_count)}</span>
        </div>
      )}

      {props.expanded && (
        <div className="-mx-4 -mb-4 mt-3">
          <ColumnStatsPanel
            column={col}
            onReprofile={props.onReprofile}
            reprofiling={props.reprofiling}
          />
        </div>
      )}
    </div>
  );
}