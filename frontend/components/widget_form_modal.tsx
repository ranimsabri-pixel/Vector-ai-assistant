"use client";

import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { toast } from "sonner";
import {
  BarChart2,
  BarChart3,
  ChevronLeft,
  Donut,
  Gauge,
  Grid3x3,
  LineChart,
  Loader2,
  PieChart,
  Radar as RadarIcon,
  ScatterChart,
  Sigma,
  Table2,
  X,
  type LucideIcon,
} from "lucide-react";

import { useAuthStore } from "@/lib/store/auth";
import { getDatasetColumns, type DatasetColumn } from "@/lib/datasets";
import {
  addWidget,
  isWidgetError,
  previewWidgetData,
  updateWidget,
  type Aggregate,
  type DashboardWidget,
  type WidgetConfig,
  type WidgetData,
  type WidgetType,
} from "@/lib/dashboards";
import { WidgetRenderer } from "@/components/widgets/widget_renderer";

const TYPE_META: { value: WidgetType; label: string; icon: LucideIcon }[] = [
  { value: "kpi", label: "KPI", icon: Gauge },
  { value: "bar_chart", label: "Barres", icon: BarChart3 },
  { value: "line_chart", label: "Courbe", icon: LineChart },
  { value: "pie_chart", label: "Circulaire", icon: PieChart },
  { value: "donut_chart", label: "Anneau", icon: Donut },
  { value: "data_table", label: "Tableau", icon: Table2 },
  { value: "radar_chart", label: "Radar", icon: RadarIcon },
  { value: "scatter_plot", label: "Nuage de points", icon: ScatterChart },
  { value: "heatmap", label: "Heatmap", icon: Grid3x3 },
  { value: "correlation_matrix", label: "Corrélation", icon: Sigma },
  { value: "histogram", label: "Histogramme", icon: BarChart2 },
];

const AGGREGATES: { value: Aggregate; label: string }[] = [
  { value: "sum", label: "Somme" },
  { value: "avg", label: "Moyenne" },
  { value: "count", label: "Nombre" },
  { value: "min", label: "Minimum" },
  { value: "max", label: "Maximum" },
];

const CORRELATION_METHODS: { value: "pearson" | "spearman" | "kendall"; label: string }[] = [
  { value: "pearson", label: "Pearson (linéaire)" },
  { value: "spearman", label: "Spearman (rangs)" },
  { value: "kendall", label: "Kendall (rangs)" },
];

type WidgetFormModalProps = {
  open: boolean;
  onClose: () => void;
  dashboardId: string;
  datasetId: string;
  widget: DashboardWidget | null; // null = creation, sinon edition
  onSaved: (widget: DashboardWidget) => void;
};

export function WidgetFormModal({
  open,
  onClose,
  dashboardId,
  datasetId,
  widget,
  onSaved,
}: WidgetFormModalProps) {
  const token = useAuthStore((s) => s.token);
  const isEditing = widget !== null;

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [title, setTitle] = useState("");
  const [widgetType, setWidgetType] = useState<WidgetType>("kpi");
  const [columns, setColumns] = useState<DatasetColumn[]>([]);
  const [loadingColumns, setLoadingColumns] = useState(false);
  const [saving, setSaving] = useState(false);

  const [previewData, setPreviewData] = useState<WidgetData | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Champs de config (superset couvrant les 11 types)
  const [column, setColumn] = useState("");
  const [aggregate, setAggregate] = useState<Aggregate>("sum");
  const [xColumn, setXColumn] = useState("");
  const [yColumn, setYColumn] = useState("");
  const [groupby, setGroupby] = useState("");
  const [categoryColumn, setCategoryColumn] = useState("");
  const [valueColumn, setValueColumn] = useState("");
  const [tableColumns, setTableColumns] = useState<Set<string>>(new Set());
  const [metricColumns, setMetricColumns] = useState<Set<string>>(new Set());
  const [sizeColumn, setSizeColumn] = useState("");
  const [colorColumn, setColorColumn] = useState("");
  const [rowColumn, setRowColumn] = useState("");
  const [colColumn, setColColumn] = useState("");
  const [corrColumns, setCorrColumns] = useState<Set<string>>(new Set());
  const [corrMethod, setCorrMethod] = useState<"pearson" | "spearman" | "kendall">("pearson");
  const [binCount, setBinCount] = useState(20);
  const [showMean, setShowMean] = useState(false);
  const [showMedian, setShowMedian] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStep(isEditing ? 2 : 1);
    setTitle(widget?.title ?? "");
    setWidgetType(widget?.widget_type ?? "kpi");
    setPreviewData(null);

    const cfg = (widget?.config ?? {}) as Record<string, unknown>;
    setColumn((cfg.column as string) ?? "");
    setAggregate((cfg.aggregate as Aggregate) ?? "sum");
    setXColumn((cfg.x_column as string) ?? "");
    setYColumn((cfg.y_column as string) ?? "");
    setGroupby((cfg.groupby as string) ?? "");
    setCategoryColumn((cfg.category_column as string) ?? "");
    setValueColumn((cfg.value_column as string) ?? "");
    setTableColumns(new Set((cfg.columns as string[]) ?? []));
    setMetricColumns(new Set((cfg.metric_columns as string[]) ?? []));
    setSizeColumn((cfg.size_column as string) ?? "");
    setColorColumn((cfg.color_column as string) ?? "");
    setRowColumn((cfg.row_column as string) ?? "");
    setColColumn((cfg.col_column as string) ?? "");
    setCorrColumns(new Set(widget?.widget_type === "correlation_matrix" ? (cfg.columns as string[]) ?? [] : []));
    setCorrMethod((cfg.method as "pearson" | "spearman" | "kendall") ?? "pearson");
    setBinCount((cfg.bin_count as number) ?? 20);
    setShowMean(Boolean(cfg.show_mean));
    setShowMedian(Boolean(cfg.show_median));

    if (!token) return;
    setLoadingColumns(true);
    getDatasetColumns(token, datasetId)
      .then(setColumns)
      .catch((e) => {
        toast.error(e instanceof Error ? e.message : "Erreur de chargement des colonnes");
      })
      .finally(() => setLoadingColumns(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, widget?.id, datasetId, token]);

  const numericColumns = useMemo(
    () => columns.filter((c) => c.dtype === "numeric"),
    [columns],
  );
  const categoricalColumns = useMemo(
    () => columns.filter((c) => ["categorical", "boolean", "datetime"].includes(c.dtype ?? "")),
    [columns],
  );

  function toggleInSet(setter: Dispatch<SetStateAction<Set<string>>>, name: string) {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  function buildConfig(): WidgetConfig | null {
    switch (widgetType) {
      case "kpi":
        if (!column) return null;
        return { column, aggregate };
      case "bar_chart":
      case "line_chart":
        if (!xColumn || !yColumn) return null;
        return { x_column: xColumn, y_column: yColumn, groupby: groupby || null, aggregate };
      case "pie_chart":
      case "donut_chart":
        if (!categoryColumn || !valueColumn) return null;
        return { category_column: categoryColumn, value_column: valueColumn, aggregate };
      case "data_table":
        if (tableColumns.size === 0) return null;
        return { columns: [...tableColumns], limit: 20 };
      case "radar_chart":
        if (!categoryColumn || metricColumns.size === 0) return null;
        return { category_column: categoryColumn, metric_columns: [...metricColumns], aggregate };
      case "scatter_plot":
        if (!xColumn || !yColumn) return null;
        return {
          x_column: xColumn,
          y_column: yColumn,
          size_column: sizeColumn || null,
          color_column: colorColumn || null,
        };
      case "heatmap":
        if (!rowColumn || !colColumn || !valueColumn) return null;
        return { row_column: rowColumn, col_column: colColumn, value_column: valueColumn, aggregate };
      case "correlation_matrix":
        if (corrColumns.size < 2) return null;
        return { columns: [...corrColumns], method: corrMethod };
      case "histogram":
        if (!column) return null;
        return { column, bin_count: binCount, show_mean: showMean, show_median: showMedian };
      default:
        return null;
    }
  }

  function goToPreview() {
    const config = buildConfig();
    if (!config) {
      toast.error("Complète la configuration du widget");
      return;
    }
    setStep(3);
    setPreviewLoading(true);
    setPreviewData(null);
    if (!token) return;
    previewWidgetData(token, dashboardId, widgetType, config)
      .then(setPreviewData)
      .catch((e) => {
        toast.error(e instanceof Error ? e.message : "Erreur de prévisualisation");
      })
      .finally(() => setPreviewLoading(false));
  }

  async function handleSave() {
    if (!token) return;
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      toast.error("Le titre du widget est obligatoire");
      return;
    }
    const config = buildConfig();
    if (!config) {
      toast.error("Complète la configuration du widget");
      return;
    }

    setSaving(true);
    try {
      const saved = isEditing
        ? await updateWidget(token, dashboardId, widget.id, { title: trimmedTitle, config })
        : await addWidget(token, dashboardId, { widget_type: widgetType, title: trimmedTitle, config });
      toast.success(isEditing ? "Widget mis à jour" : "Widget ajouté");
      onSaved(saved);
      onClose();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur d'enregistrement");
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  const STEP_TITLES: Record<1 | 2 | 3, string> = {
    1: "Choisis un type de widget",
    2: "Configure le widget",
    3: "Aperçu",
  };

  const previewWidget: DashboardWidget = {
    id: "preview",
    widget_type: widgetType,
    title: title || "Aperçu",
    config: buildConfig() ?? ({} as WidgetConfig),
    position: 0,
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/60 z-40 animate-fade-in" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="w-full max-w-lg bg-card border border-border rounded-2xl shadow-2xl animate-message-in pointer-events-auto overflow-hidden flex flex-col max-h-[85vh]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-5 border-b border-border shrink-0">
            <div className="flex items-center gap-2">
              {step > 1 && !(step === 2 && isEditing) && (
                <button
                  onClick={() => setStep((s) => (s === 3 ? 2 : 1) as 1 | 2 | 3)}
                  className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground transition-colors"
                  aria-label="Précédent"
                >
                  <ChevronLeft size={16} />
                </button>
              )}
              <div>
                <h2 className="text-base font-semibold text-foreground">
                  {isEditing ? "Modifier le widget" : STEP_TITLES[step]}
                </h2>
                {!isEditing && (
                  <p className="text-[11px] text-muted-foreground mt-0.5">Étape {step} / 3</p>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Fermer"
            >
              <X size={16} />
            </button>
          </div>

          <div className="p-5 space-y-4 overflow-y-auto">
            {step === 1 && (
              <div className="grid grid-cols-3 gap-2">
                {TYPE_META.map((t) => {
                  const Icon = t.icon;
                  const selected = widgetType === t.value;
                  return (
                    <button
                      key={t.value}
                      type="button"
                      onClick={() => {
                        setWidgetType(t.value);
                        setStep(2);
                      }}
                      className={`flex flex-col items-center gap-2 p-3 rounded-lg border transition-colors ${
                        selected
                          ? "bg-emerald-600/10 border-emerald-600/40 text-emerald-400"
                          : "bg-background border-border text-muted-foreground hover:border-border hover:text-foreground"
                      }`}
                    >
                      <Icon size={20} />
                      <span className="text-[11px] font-medium text-center">{t.label}</span>
                    </button>
                  );
                })}
              </div>
            )}

            {step === 2 && (
              <>
                <div>
                  <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                    Titre
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Ex: Chiffre d'affaires total"
                    autoFocus
                    className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
                  />
                </div>

                {loadingColumns ? (
                  <div className="flex items-center justify-center gap-2 py-4 text-xs text-muted-foreground">
                    <Loader2 size={14} className="animate-spin" />
                    Chargement des colonnes...
                  </div>
                ) : (
                  <>
                    {widgetType === "kpi" && (
                      <>
                        <ColumnSelect
                          label="Colonne numérique"
                          value={column}
                          onChange={setColumn}
                          options={numericColumns}
                        />
                        <AggregateSelect value={aggregate} onChange={setAggregate} />
                      </>
                    )}

                    {(widgetType === "bar_chart" || widgetType === "line_chart") && (
                      <>
                        <ColumnSelect
                          label="Colonne X (catégorie / date)"
                          value={xColumn}
                          onChange={setXColumn}
                          options={columns}
                        />
                        <ColumnSelect
                          label="Colonne Y (valeur numérique)"
                          value={yColumn}
                          onChange={setYColumn}
                          options={numericColumns}
                        />
                        <ColumnSelect
                          label="Regrouper par (optionnel)"
                          value={groupby}
                          onChange={setGroupby}
                          options={categoricalColumns}
                          allowEmpty
                        />
                        <AggregateSelect value={aggregate} onChange={setAggregate} />
                      </>
                    )}

                    {(widgetType === "pie_chart" || widgetType === "donut_chart") && (
                      <>
                        <ColumnSelect
                          label="Colonne de catégorie"
                          value={categoryColumn}
                          onChange={setCategoryColumn}
                          options={categoricalColumns}
                        />
                        <ColumnSelect
                          label="Colonne de valeur"
                          value={valueColumn}
                          onChange={setValueColumn}
                          options={numericColumns}
                        />
                        <AggregateSelect value={aggregate} onChange={setAggregate} />
                      </>
                    )}

                    {widgetType === "data_table" && (
                      <MultiColumnSelect
                        label="Colonnes à afficher"
                        options={columns}
                        selected={tableColumns}
                        onToggle={(name) => toggleInSet(setTableColumns, name)}
                      />
                    )}

                    {widgetType === "radar_chart" && (
                      <>
                        <ColumnSelect
                          label="Colonne de catégorie"
                          value={categoryColumn}
                          onChange={setCategoryColumn}
                          options={categoricalColumns}
                        />
                        <MultiColumnSelect
                          label="Colonnes métriques (numériques)"
                          options={numericColumns}
                          selected={metricColumns}
                          onToggle={(name) => toggleInSet(setMetricColumns, name)}
                        />
                        <AggregateSelect value={aggregate} onChange={setAggregate} />
                      </>
                    )}

                    {widgetType === "scatter_plot" && (
                      <>
                        <ColumnSelect
                          label="Colonne X (numérique)"
                          value={xColumn}
                          onChange={setXColumn}
                          options={numericColumns}
                        />
                        <ColumnSelect
                          label="Colonne Y (numérique)"
                          value={yColumn}
                          onChange={setYColumn}
                          options={numericColumns}
                        />
                        <ColumnSelect
                          label="Taille des points (optionnel)"
                          value={sizeColumn}
                          onChange={setSizeColumn}
                          options={numericColumns}
                          allowEmpty
                        />
                        <ColumnSelect
                          label="Couleur par catégorie (optionnel)"
                          value={colorColumn}
                          onChange={setColorColumn}
                          options={categoricalColumns}
                          allowEmpty
                        />
                      </>
                    )}

                    {widgetType === "heatmap" && (
                      <>
                        <ColumnSelect
                          label="Colonne des lignes"
                          value={rowColumn}
                          onChange={setRowColumn}
                          options={categoricalColumns}
                        />
                        <ColumnSelect
                          label="Colonne des colonnes"
                          value={colColumn}
                          onChange={setColColumn}
                          options={categoricalColumns}
                        />
                        <ColumnSelect
                          label="Colonne de valeur"
                          value={valueColumn}
                          onChange={setValueColumn}
                          options={numericColumns}
                        />
                        <AggregateSelect value={aggregate} onChange={setAggregate} />
                      </>
                    )}

                    {widgetType === "correlation_matrix" && (
                      <>
                        <MultiColumnSelect
                          label="Colonnes numériques (min. 2)"
                          options={numericColumns}
                          selected={corrColumns}
                          onToggle={(name) => toggleInSet(setCorrColumns, name)}
                        />
                        <div>
                          <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                            Méthode
                          </label>
                          <select
                            value={corrMethod}
                            onChange={(e) => setCorrMethod(e.target.value as typeof corrMethod)}
                            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
                          >
                            {CORRELATION_METHODS.map((m) => (
                              <option key={m.value} value={m.value}>
                                {m.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </>
                    )}

                    {widgetType === "histogram" && (
                      <>
                        <ColumnSelect
                          label="Colonne numérique"
                          value={column}
                          onChange={setColumn}
                          options={numericColumns}
                        />
                        <div>
                          <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                            Nombre de tranches (bins)
                          </label>
                          <input
                            type="number"
                            min={2}
                            max={100}
                            value={binCount}
                            onChange={(e) => setBinCount(Number(e.target.value) || 20)}
                            className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
                          />
                        </div>
                        <div className="flex items-center gap-4">
                          <label className="flex items-center gap-2 text-xs text-muted-foreground">
                            <input
                              type="checkbox"
                              checked={showMean}
                              onChange={(e) => setShowMean(e.target.checked)}
                              className="accent-emerald-600"
                            />
                            Afficher la moyenne
                          </label>
                          <label className="flex items-center gap-2 text-xs text-muted-foreground">
                            <input
                              type="checkbox"
                              checked={showMedian}
                              onChange={(e) => setShowMedian(e.target.checked)}
                              className="accent-emerald-600"
                            />
                            Afficher la médiane
                          </label>
                        </div>
                      </>
                    )}
                  </>
                )}
              </>
            )}

            {step === 3 && (
              <div className="h-64 bg-background/50 border border-border rounded-lg p-3">
                {previewLoading ? (
                  <div className="h-full flex items-center justify-center">
                    <Loader2 size={20} className="animate-spin text-emerald-400" />
                  </div>
                ) : previewData ? (
                  isWidgetError(previewData) ? (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground text-center px-4">
                      {previewData.error}
                    </div>
                  ) : (
                    <WidgetRenderer widget={previewWidget} data={previewData} />
                  )
                ) : null}
              </div>
            )}
          </div>

          <div className="flex gap-2 p-4 bg-background/50 border-t border-border shrink-0">
            <button
              onClick={onClose}
              disabled={saving}
              className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors disabled:opacity-40"
            >
              Annuler
            </button>
            {step === 2 && (
              <button
                onClick={goToPreview}
                className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 transition-colors"
              >
                Aperçu
              </button>
            )}
            {step === 3 && (
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {saving && <Loader2 size={14} className="animate-spin" />}
                Enregistrer
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function ColumnSelect({
  label,
  value,
  onChange,
  options,
  allowEmpty,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: DatasetColumn[];
  allowEmpty?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
      >
        <option value="">{allowEmpty ? "Aucune" : "Sélectionner..."}</option>
        {options.map((c) => (
          <option key={c.id} value={c.name}>
            {c.name}
          </option>
        ))}
      </select>
    </div>
  );
}

function MultiColumnSelect({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string;
  options: DatasetColumn[];
  selected: Set<string>;
  onToggle: (name: string) => void;
}) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
        {label}
      </label>
      <div className="border border-border rounded-lg max-h-48 overflow-y-auto divide-y divide-border">
        {options.map((c) => {
          const checked = selected.has(c.name);
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => onToggle(c.name)}
              className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-muted/50 transition-colors text-left"
            >
              <div
                className={`w-4 h-4 rounded flex items-center justify-center shrink-0 border ${
                  checked ? "bg-emerald-600 border-emerald-600" : "border-border"
                }`}
              />
              <span className="text-xs text-foreground truncate">{c.name}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function AggregateSelect({
  value,
  onChange,
}: {
  value: Aggregate;
  onChange: (v: Aggregate) => void;
}) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
        Agrégation
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as Aggregate)}
        className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
      >
        {AGGREGATES.map((a) => (
          <option key={a.value} value={a.value}>
            {a.label}
          </option>
        ))}
      </select>
    </div>
  );
}
