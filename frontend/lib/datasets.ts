import { api, ApiError, API_BASE_URL } from "@/lib/api";

// ============================================================
// Types — Dataset (S2)
// ============================================================

export type Dataset = {
  id: string;
  name: string;
  description: string | null;
  original_filename: string;
  file_size_bytes: number;
  row_count: number | null;
  column_count: number | null;
  status: string;
  quality_score: number | null;
  created_at: string;
  semantic_analysis: SemanticAnalysis | null;
  auto_kpis: AutoKpis | null;
};

export type DatasetDetail = Dataset & {
  user_id: string;
  file_path: string;
  error_message: string | null;
  quality_issues: Record<string, unknown> | null;
  raw_data_sample: {
    columns: string[];
    rows: string[][];
  } | null;
  updated_at: string;
  semantic_analysis: SemanticAnalysis | null;
  auto_kpis: AutoKpis | null;
};

/**
 * Résumé léger d'un dataset pour les formulaires (J19).
 * Tous les champs optionnels pour rester compatibles avec différents endpoints
 * (GET /datasets retourne Dataset[], le tool list_user_datasets retourne autre chose).
 */
export type DatasetSummary = {
  id: string;
  name: string;
  status: string;
  created_at: string;
  domain?: string;
  rows?: number | null;
  columns?: number | null;
  quality?: number;
  matches_for_action?: string[];
};

// ============================================================
// Upload + CRUD (S2 J6)
// ============================================================

export type ColumnOverride = {
  original_name: string;
  new_name?: string;
  type?: string;
  deleted?: boolean;
};

export async function uploadDataset(
  token: string,
  file: File,
  name?: string,
  description?: string,
  columnOverrides?: ColumnOverride[]
): Promise<DatasetDetail> {
  const formData = new FormData();
  formData.append("file", file);
  if (name) formData.append("name", name);
  if (description) formData.append("description", description);
  if (columnOverrides && columnOverrides.length > 0) {
    formData.append("column_overrides", JSON.stringify(columnOverrides));
  }

  return api<DatasetDetail>("/datasets/upload", {
    method: "POST",
    body: formData,
    token,
  });
}

export async function listDatasets(token: string): Promise<Dataset[]> {
  return api<Dataset[]>("/datasets", { token });
}

export async function getDataset(
  token: string,
  id: string
): Promise<DatasetDetail> {
  return api<DatasetDetail>(`/datasets/${id}`, { token });
}

export async function deleteDataset(token: string, id: string): Promise<void> {
  return api<void>(`/datasets/${id}`, { method: "DELETE", token });
}

// ============================================================
// Colonnes (S2 J7)
// ============================================================

export type NumericStats = {
  min: number;
  max: number;
  mean: number;
  median: number;
  std_dev: number;
  p25: number;
  p75: number;
  histogram_bins: { bin_start: number; bin_end: number; count: number }[];
};

export type CategoricalStats = {
  top_values: { value: string; count: number }[];
  total_unique: number;
};

export type DateStats = {
  min_date: string;
  max_date: string;
  date_distribution: { period: string; count: number }[];
};

export type DatasetColumn = {
  id: string;
  dataset_id: string;
  name: string;
  dtype: string | null;
  is_nullable: boolean | null;
  is_date_main: boolean | null;
  null_count: number | null;
  unique_count: number | null;
  sample_values: {
    samples?: unknown[];
    stats?: Record<string, unknown>;
  } | null;
  numeric_stats?: NumericStats | null;
  categorical_stats?: CategoricalStats | null;
  date_stats?: DateStats | null;
};

// ============================================================
// Statistiques enrichies + export sample (S5 J39)
// ============================================================

export async function reprofileDataset(
  token: string,
  id: string
): Promise<DatasetDetail> {
  return api<DatasetDetail>(`/datasets/${id}/reprofile`, {
    method: "POST",
    token,
  });
}

/**
 * Télécharge un échantillon CSV du dataset (100/500/1000 lignes) et
 * déclenche le téléchargement dans le navigateur.
 */
export async function downloadDatasetSample(
  token: string,
  id: string,
  datasetName: string,
  limit: number
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/datasets/${id}/sample?limit=${limit}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );

  if (!response.ok) {
    let detail = "Erreur lors de l'export";
    try {
      const data = await response.json();
      detail = data?.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${datasetName}_sample_${limit}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export async function profileDataset(
  token: string,
  id: string
): Promise<DatasetDetail> {
  return api<DatasetDetail>(`/datasets/${id}/profile`, {
    method: "POST",
    token,
  });
}

export async function getDatasetColumns(
  token: string,
  id: string
): Promise<DatasetColumn[]> {
  return api<DatasetColumn[]>(`/datasets/${id}/columns`, { token });
}

/**
 * Corrige les colonnes d'un dataset déjà profilé (renommer / supprimer /
 * forcer un type) puis relance automatiquement le profilage côté serveur.
 * Utiliser pollDatasetStatus() ensuite pour attendre status='ready'.
 */
export async function updateDatasetColumns(
  token: string,
  id: string,
  overrides: ColumnOverride[]
): Promise<DatasetDetail> {
  return api<DatasetDetail>(`/datasets/${id}/columns`, {
    method: "PATCH",
    body: JSON.stringify({ overrides }),
    token,
  });
}

/**
 * Poll le statut d'un dataset jusqu'à 'ready' (par défaut toutes les 3s).
 * Utilisé après update_column_overrides pour attendre la fin du re-profilage.
 */
export async function pollDatasetStatus(
  token: string,
  id: string,
  options: { maxAttempts?: number; intervalMs?: number } = {},
): Promise<DatasetDetail> {
  const { maxAttempts = 20, intervalMs = 3000 } = options;

  for (let i = 0; i < maxAttempts; i++) {
    const dataset = await getDataset(token, id);

    if (dataset.status === "ready") return dataset;
    if (dataset.status === "error") {
      throw new Error(
        dataset.error_message ?? "Le profilage du dataset a échoué"
      );
    }

    await new Promise((r) => setTimeout(r, intervalMs));
  }

  throw new Error(
    "Le profilage du dataset prend trop de temps. Réessaie plus tard."
  );
}

export async function getColumnValues(
  token: string,
  id: string,
  columnName: string
): Promise<(string | number | boolean)[]> {
  return api<(string | number | boolean)[]>(
    `/datasets/${id}/columns/${encodeURIComponent(columnName)}/values`,
    { token }
  );
}

// ============================================================
// Analyse sémantique (S2 J9)
// ============================================================

export type SuggestedKPI = {
  name: string;
  description: string;
  columns_used: string[];
  priority: "high" | "medium" | "low";
};

export type SemanticAnalysis = {
  rule_based: {
    primary_domain: string;
    rule_scores: Record<string, number>;
    confidence: number;
  };
  llm_analysis: {
    domain: string;
    domain_label: string;
    description: string;
    key_columns: string[];
    suggested_kpis: SuggestedKPI[];
    warnings: string[];
  };
  analyzed_at: string;
};

export async function analyzeDataset(
  token: string,
  id: string
): Promise<DatasetDetail> {
  return api<DatasetDetail>(`/datasets/${id}/analyze`, {
    method: "POST",
    token,
  });
}

// ============================================================
// KPIs (S3)
// ============================================================

export type KPISpec = {
  id: string;
  title: string;
  description: string;
  type:
    | "count"
    | "count_distinct"
    | "sum"
    | "mean"
    | "median"
    | "min"
    | "max"
    | "nonnull_rate"
    | "true_rate"
    | "ratio"
    | "breakdown"
    | "trend";
  column: string | null;
  filter: { column: string; value: unknown; op?: string } | null;
  group_by: string | null;
  aggregation: string | null;
  time_column: string | null;
  granularity: string | null;
  top_n: number | null;
  unit: string | null;
  icon: string | null;
  category: string;
};

export type KPIResult = {
  spec_id: string;
  value: number | string;
  raw_value: number | null;
  formatted: string;
  unit: string | null;
  chart_type: "number" | "bar" | "line";
  metadata: Record<string, unknown> | null;
};

export type AutoKpis = {
  specs: KPISpec[];
  generated_count: number;
};

export async function generateAutoKpis(
  token: string,
  id: string
): Promise<DatasetDetail> {
  return api<DatasetDetail>(`/datasets/${id}/auto-kpis/generate`, {
    method: "POST",
    token,
  });
}

export async function generateAdvancedKpis(
  token: string,
  id: string
): Promise<DatasetDetail> {
  return api<DatasetDetail>(`/datasets/${id}/advanced-kpis/generate`, {
    method: "POST",
    token,
  });
}

export async function calculateAllKpis(
  token: string,
  id: string
): Promise<KPIResult[]> {
  return api<KPIResult[]>(`/datasets/${id}/auto-kpis/calculate-all`, {
    method: "POST",
    token,
  });
}

export async function calculateOneKpi(
  token: string,
  datasetId: string,
  specId: string
): Promise<KPIResult> {
  return api<KPIResult>(
    `/datasets/${datasetId}/auto-kpis/${specId}/calculate`,
    {
      method: "POST",
      token,
    }
  );
}

// ============================================================
// Dashboards persistants (J14)
// ============================================================

export type Dashboard = {
  id: string;
  user_id: string;
  dataset_id: string;
  title: string;
  kpi_specs: KPISpec[] | null;
  kpi_results: KPIResult[] | null;
  generated_at: string | null;
  created_at: string;
};

export async function saveDashboard(
  token: string,
  payload: {
    dataset_id: string;
    title: string;
    kpi_specs: KPISpec[];
    kpi_results: KPIResult[];
  }
): Promise<Dashboard> {
  return api<Dashboard>("/dashboards/save", {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export async function getDashboardByDataset(
  token: string,
  datasetId: string
): Promise<Dashboard | null> {
  return api<Dashboard | null>(`/dashboards/by-dataset/${datasetId}`, {
    token,
  });
}

export async function listDashboards(token: string): Promise<Dashboard[]> {
  return api<Dashboard[]>("/dashboards", { token });
}

export async function deleteDashboard(
  token: string,
  dashboardId: string
): Promise<void> {
  return api<void>(`/dashboards/${dashboardId}`, {
    method: "DELETE",
    token,
  });
}

// ============================================================
// J19 — Helpers pour formulaires conversationnels
// ============================================================

/**
 * Liste tous les datasets de l'utilisateur (alias de listDatasets avec
 * le type DatasetSummary plus léger).
 * Filtre côté frontend pour ne garder que les status='ready'.
 */
export async function fetchUserDatasets(
  token: string,
): Promise<DatasetSummary[]> {
  const list = await listDatasets(token);
  return list as DatasetSummary[];
}

/**
 * Lance le profilage d'un dataset puis poll jusqu'à status='ready'.
 * Utilisé après un upload direct dans un formulaire d'action rapide.
 */
export async function pollDatasetReady(
  datasetId: string,
  token: string,
  options: { maxAttempts?: number; intervalMs?: number } = {},
): Promise<DatasetSummary> {
  const { maxAttempts = 30, intervalMs = 1000 } = options;

  // 1. Déclenche le profilage explicitement
  await profileDataset(token, datasetId);

  // 2. Poll le statut jusqu'à 'ready' ou 'error'
  for (let i = 0; i < maxAttempts; i++) {
    const dataset = await getDataset(token, datasetId);

    if (dataset.status === "ready") return dataset as DatasetSummary;
    if (dataset.status === "error") {
      throw new Error(
        dataset.error_message ??
          "Le profilage du dataset a échoué côté serveur",
      );
    }

    await new Promise((r) => setTimeout(r, intervalMs));
  }

  throw new Error(
    "Le profilage du dataset prend trop de temps. Réessayez plus tard.",
  );
}