"use client";

import { api, ApiError } from "./api";

// ============================================================
// Types partagés
// ============================================================

export type Aggregate = "sum" | "avg" | "count" | "min" | "max";

export type WidgetType =
  | "kpi"
  | "bar_chart"
  | "line_chart"
  | "pie_chart"
  | "data_table"
  | "donut_chart"
  | "radar_chart"
  | "scatter_plot"
  | "heatmap"
  | "correlation_matrix"
  | "histogram";

// Palette cyclique pour les séries multi-couleurs (charte visuelle produit)
export const CHART_COLORS = [
  "#10b981", // emerald
  "#3b82f6", // blue
  "#f59e0b", // amber
  "#ef4444", // red
  "#a855f7", // purple
  "#14b8a6", // teal
];

// ============================================================
// Config par type de widget (reflète widget_compute.py)
// ============================================================

export type KpiConfig = { column: string; aggregate: Aggregate };
export type BarLineConfig = {
  x_column: string;
  y_column: string;
  groupby?: string | null;
  aggregate: Aggregate;
};
export type PieConfig = {
  category_column: string;
  value_column: string;
  aggregate: Aggregate;
};
export type DataTableConfig = {
  columns: string[];
  limit?: number;
  sort_by?: string | null;
  sort_order?: "asc" | "desc";
};
export type RadarConfig = {
  category_column: string;
  metric_columns: string[];
  aggregate: Aggregate;
};
export type ScatterConfig = {
  x_column: string;
  y_column: string;
  size_column?: string | null;
  color_column?: string | null;
};
export type HeatmapConfig = {
  row_column: string;
  col_column: string;
  value_column: string;
  aggregate: Aggregate;
  color_scale?: string;
};
export type CorrelationMatrixConfig = {
  columns: string[];
  method?: "pearson" | "spearman" | "kendall";
};
export type HistogramConfig = {
  column: string;
  bin_count?: number;
  show_mean?: boolean;
  show_median?: boolean;
};

export type WidgetConfig =
  | KpiConfig
  | BarLineConfig
  | PieConfig
  | DataTableConfig
  | RadarConfig
  | ScatterConfig
  | HeatmapConfig
  | CorrelationMatrixConfig
  | HistogramConfig;

// ============================================================
// Données calculées par type de widget (réponse de /data)
// ============================================================

export type KpiData = { value: number; trend: number | null };
export type BarLineData = {
  labels: string[];
  values?: number[];
  series?: { name: string; data: number[] }[];
};
export type PieData = {
  labels: string[];
  values: number[];
  total: number;
  percentages: number[];
};
export type DataTableData = { columns: string[]; rows: (string | number | boolean | null)[][] };
export type RadarData = {
  axes: string[];
  series: { name: string; values: number[] }[];
};
export type ScatterPoint = { x: number; y: number; size?: number; color?: string };
export type ScatterData = {
  points: ScatterPoint[];
  x_label: string;
  y_label: string;
  has_size: boolean;
  has_color: boolean;
};
export type HeatmapData = {
  rows: string[];
  cols: string[];
  values: number[][];
  min: number;
  max: number;
  color_scale: string;
};
export type CorrelationMatrixData = { columns: string[]; matrix: number[][]; method: string };
export type HistogramData = {
  bins: string[];
  counts: number[];
  mean: number | null;
  median: number | null;
};
export type WidgetError = { error: string };

export type WidgetData =
  | KpiData
  | BarLineData
  | PieData
  | DataTableData
  | RadarData
  | ScatterData
  | HeatmapData
  | CorrelationMatrixData
  | HistogramData
  | WidgetError;

export function isWidgetError(data: WidgetData): data is WidgetError {
  return typeof data === "object" && data !== null && "error" in data;
}

// ============================================================
// Dashboard / Widget — types API
// ============================================================

export type DashboardWidget = {
  id: string;
  widget_type: WidgetType;
  title: string;
  config: WidgetConfig;
  position: number;
};

export type SavedDashboardSummary = {
  id: string;
  name: string;
  description: string | null;
  dataset_id: string;
  dataset_name: string;
  widget_count: number;
  created_at: string;
  updated_at: string;
};

export type SavedDashboardDetail = SavedDashboardSummary & {
  widgets: DashboardWidget[];
};

export type DashboardFilter = {
  column: string;
  op: "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "in" | "between";
  value: unknown;
};

export type CreateWidgetPayload = {
  widget_type: WidgetType;
  title: string;
  config: WidgetConfig;
  position?: number;
};

export type UpdateWidgetPayload = {
  title?: string;
  config?: WidgetConfig;
  position?: number;
};

// ============================================================
// Persistance des filtres dans l'URL (liens partageables)
// ============================================================

export function encodeFiltersParam(filters: DashboardFilter[]): string | null {
  if (filters.length === 0) return null;
  const json = encodeURIComponent(JSON.stringify(filters));
  return btoa(unescape(json));
}

export function decodeFiltersParam(param: string | null): DashboardFilter[] {
  if (!param) return [];
  try {
    const json = escape(atob(param));
    return JSON.parse(decodeURIComponent(json));
  } catch {
    return [];
  }
}

// ============================================================
// CRUD dashboards
// ============================================================

export async function listSavedDashboards(
  token: string
): Promise<SavedDashboardSummary[]> {
  return api<SavedDashboardSummary[]>("/saved-dashboards", { token });
}

export async function getSavedDashboard(
  token: string,
  dashboardId: string
): Promise<SavedDashboardDetail> {
  return api<SavedDashboardDetail>(`/saved-dashboards/${dashboardId}`, {
    token,
  });
}

export async function createSavedDashboard(
  token: string,
  payload: {
    name: string;
    description?: string | null;
    dataset_id: string;
    widgets?: CreateWidgetPayload[];
  }
): Promise<SavedDashboardDetail> {
  return api<SavedDashboardDetail>("/saved-dashboards", {
    method: "POST",
    token,
    body: {
      name: payload.name,
      description: payload.description ?? null,
      dataset_id: payload.dataset_id,
      widgets: payload.widgets ?? [],
    },
  });
}

export async function updateSavedDashboard(
  token: string,
  dashboardId: string,
  payload: { name?: string; description?: string | null }
): Promise<SavedDashboardDetail> {
  return api<SavedDashboardDetail>(`/saved-dashboards/${dashboardId}`, {
    method: "PATCH",
    token,
    body: payload,
  });
}

export async function deleteSavedDashboard(
  token: string,
  dashboardId: string
): Promise<void> {
  await api<void>(`/saved-dashboards/${dashboardId}`, {
    method: "DELETE",
    token,
  });
}

// ============================================================
// Données calculées (KPI/charts, avec filtres optionnels)
// ============================================================

function filtersToQuery(filters?: DashboardFilter[] | null): string {
  if (!filters || filters.length === 0) return "";
  return `?filters=${encodeURIComponent(JSON.stringify(filters))}`;
}

export async function getDashboardData(
  token: string,
  dashboardId: string,
  filters?: DashboardFilter[] | null
): Promise<Record<string, WidgetData>> {
  return api<Record<string, WidgetData>>(
    `/saved-dashboards/${dashboardId}/data${filtersToQuery(filters)}`,
    { token }
  );
}

export async function getWidgetData(
  token: string,
  dashboardId: string,
  widgetId: string,
  filters?: DashboardFilter[] | null
): Promise<WidgetData> {
  return api<WidgetData>(
    `/saved-dashboards/${dashboardId}/widgets/${widgetId}/data${filtersToQuery(
      filters
    )}`,
    { token }
  );
}

export async function exportDashboardCsv(
  token: string,
  dashboardId: string,
  filters?: DashboardFilter[] | null
): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(
    `${
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    }/saved-dashboards/${dashboardId}/export-data${filtersToQuery(filters)}`,
    { headers: { Authorization: "Bearer " + token } }
  );
  if (!res.ok) {
    throw new ApiError(res.status, "Erreur lors de l'export CSV");
  }
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="(.+)"/);
  const filename = match ? match[1] : "export.csv";
  const blob = await res.blob();
  return { blob, filename };
}

export async function previewWidgetData(
  token: string,
  dashboardId: string,
  widgetType: WidgetType,
  config: WidgetConfig
): Promise<WidgetData> {
  return api<WidgetData>(`/saved-dashboards/${dashboardId}/preview`, {
    method: "POST",
    token,
    body: { widget_type: widgetType, config },
  });
}

// ============================================================
// CRUD widgets
// ============================================================

export async function addWidget(
  token: string,
  dashboardId: string,
  payload: CreateWidgetPayload
): Promise<DashboardWidget> {
  return api<DashboardWidget>(`/saved-dashboards/${dashboardId}/widgets`, {
    method: "POST",
    token,
    body: payload,
  });
}

export async function updateWidget(
  token: string,
  dashboardId: string,
  widgetId: string,
  payload: UpdateWidgetPayload
): Promise<DashboardWidget> {
  return api<DashboardWidget>(
    `/saved-dashboards/${dashboardId}/widgets/${widgetId}`,
    { method: "PATCH", token, body: payload }
  );
}

export async function deleteWidget(
  token: string,
  dashboardId: string,
  widgetId: string
): Promise<void> {
  await api<void>(`/saved-dashboards/${dashboardId}/widgets/${widgetId}`, {
    method: "DELETE",
    token,
  });
}

export async function reorderWidgets(
  token: string,
  dashboardId: string,
  widgetIds: string[]
): Promise<SavedDashboardDetail> {
  return api<SavedDashboardDetail>(
    `/saved-dashboards/${dashboardId}/widgets/reorder`,
    { method: "POST", token, body: { widget_ids: widgetIds } }
  );
}
