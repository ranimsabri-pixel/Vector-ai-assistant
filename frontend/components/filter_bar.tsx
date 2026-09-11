"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Filter, Loader2, Plus, X } from "lucide-react";

import { useAuthStore } from "@/lib/store/auth";
import { getColumnValues, type DatasetColumn } from "@/lib/datasets";
import type { DashboardFilter } from "@/lib/dashboards";

type FilterBarProps = {
  datasetId: string;
  columns: DatasetColumn[];
  filters: DashboardFilter[];
  onChange: (filters: DashboardFilter[]) => void;
};

function formatFilterLabel(f: DashboardFilter): string {
  switch (f.op) {
    case "eq":
      return `${f.column} = ${f.value}`;
    case "neq":
      return `${f.column} ≠ ${f.value}`;
    case "gt":
      return `${f.column} > ${f.value}`;
    case "gte":
      return `${f.column} ≥ ${f.value}`;
    case "lt":
      return `${f.column} < ${f.value}`;
    case "lte":
      return `${f.column} ≤ ${f.value}`;
    case "in": {
      const values = f.value as unknown[];
      const shown = values.slice(0, 3).join(", ");
      return `${f.column} : ${shown}${values.length > 3 ? ` +${values.length - 3}` : ""}`;
    }
    case "between": {
      const [lo, hi] = f.value as [unknown, unknown];
      return `${f.column} : ${lo} — ${hi}`;
    }
    default:
      return f.column;
  }
}

export function FilterBar({ datasetId, columns, filters, onChange }: FilterBarProps) {
  const token = useAuthStore((s) => s.token);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerColumn, setPickerColumn] = useState<DatasetColumn | null>(null);

  const [values, setValues] = useState<(string | number | boolean)[]>([]);
  const [loadingValues, setLoadingValues] = useState(false);
  const [selectedValues, setSelectedValues] = useState<Set<string>>(new Set());
  const [minVal, setMinVal] = useState("");
  const [maxVal, setMaxVal] = useState("");

  useEffect(() => {
    if (!pickerColumn || !token) return;
    if (pickerColumn.dtype === "numeric" || pickerColumn.dtype === "datetime") return;
    setLoadingValues(true);
    getColumnValues(token, datasetId, pickerColumn.name)
      .then(setValues)
      .catch((e) => toast.error(e instanceof Error ? e.message : "Erreur de chargement des valeurs"))
      .finally(() => setLoadingValues(false));
  }, [pickerColumn, datasetId, token]);

  function resetPicker() {
    setPickerOpen(false);
    setPickerColumn(null);
    setValues([]);
    setSelectedValues(new Set());
    setMinVal("");
    setMaxVal("");
  }

  function toggleValue(v: string) {
    setSelectedValues((prev) => {
      const next = new Set(prev);
      if (next.has(v)) next.delete(v);
      else next.add(v);
      return next;
    });
  }

  function applyFilter() {
    if (!pickerColumn) return;
    let newFilter: DashboardFilter | null = null;

    if (pickerColumn.dtype === "numeric" || pickerColumn.dtype === "datetime") {
      if (!minVal && !maxVal) {
        toast.error("Renseigne au moins une borne");
        return;
      }
      const lo = minVal || (pickerColumn.dtype === "numeric" ? "-1e18" : "0000-01-01");
      const hi = maxVal || (pickerColumn.dtype === "numeric" ? "1e18" : "9999-12-31");
      newFilter = { column: pickerColumn.name, op: "between", value: [lo, hi] };
    } else {
      if (selectedValues.size === 0) {
        toast.error("Sélectionne au moins une valeur");
        return;
      }
      newFilter = { column: pickerColumn.name, op: "in", value: [...selectedValues] };
    }

    onChange([...filters.filter((f) => f.column !== pickerColumn.name), newFilter]);
    resetPicker();
  }

  function removeFilter(column: string) {
    onChange(filters.filter((f) => f.column !== column));
  }

  return (
    <div className="flex items-center gap-2 flex-wrap mb-6">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground shrink-0">
        <Filter size={13} />
        Filtres
      </div>

      {filters.map((f) => (
        <span
          key={f.column}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-emerald-600/10 text-emerald-400 border border-emerald-600/30"
        >
          {formatFilterLabel(f)}
          <button
            onClick={() => removeFilter(f.column)}
            className="hover:text-emerald-200 transition-colors"
            aria-label={`Retirer le filtre ${f.column}`}
          >
            <X size={12} />
          </button>
        </span>
      ))}

      <div className="relative">
        <button
          onClick={() => setPickerOpen((o) => !o)}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs bg-card border border-border text-muted-foreground hover:text-foreground hover:border-border transition-colors"
        >
          <Plus size={12} />
          Ajouter un filtre
        </button>

        {pickerOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={resetPicker} />
            <div className="absolute z-50 top-full left-0 mt-2 w-72 bg-card border border-border rounded-xl shadow-2xl p-3">
              {!pickerColumn ? (
                <div className="space-y-0.5 max-h-64 overflow-y-auto">
                  {columns.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => setPickerColumn(c)}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs text-foreground hover:bg-muted transition-colors flex items-center justify-between"
                    >
                      {c.name}
                      <span className="text-[10px] text-muted-foreground uppercase">{c.dtype}</span>
                    </button>
                  ))}
                </div>
              ) : pickerColumn.dtype === "numeric" || pickerColumn.dtype === "datetime" ? (
                <div className="space-y-3">
                  <p className="text-xs font-medium text-foreground">{pickerColumn.name}</p>
                  <div className="flex items-center gap-2">
                    <input
                      type={pickerColumn.dtype === "datetime" ? "date" : "number"}
                      value={minVal}
                      onChange={(e) => setMinVal(e.target.value)}
                      placeholder="Min"
                      className="w-full px-2 py-1.5 bg-background border border-border rounded-lg text-xs text-foreground focus:outline-none focus:border-emerald-500/60"
                    />
                    <span className="text-muted-foreground text-xs">—</span>
                    <input
                      type={pickerColumn.dtype === "datetime" ? "date" : "number"}
                      value={maxVal}
                      onChange={(e) => setMaxVal(e.target.value)}
                      placeholder="Max"
                      className="w-full px-2 py-1.5 bg-background border border-border rounded-lg text-xs text-foreground focus:outline-none focus:border-emerald-500/60"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPickerColumn(null)}
                      className="flex-1 px-3 py-1.5 rounded-lg text-xs text-muted-foreground hover:bg-muted transition-colors"
                    >
                      Retour
                    </button>
                    <button
                      onClick={applyFilter}
                      className="flex-1 px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-500 transition-colors"
                    >
                      Appliquer
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs font-medium text-foreground">{pickerColumn.name}</p>
                  {loadingValues ? (
                    <div className="flex items-center justify-center gap-2 py-4 text-xs text-muted-foreground">
                      <Loader2 size={13} className="animate-spin" />
                      Chargement...
                    </div>
                  ) : (
                    <div className="max-h-48 overflow-y-auto border border-border rounded-lg divide-y divide-border">
                      {values.map((v) => {
                        const key = String(v);
                        const checked = selectedValues.has(key);
                        return (
                          <button
                            key={key}
                            onClick={() => toggleValue(key)}
                            className="w-full flex items-center gap-2 px-2.5 py-1.5 hover:bg-muted/50 transition-colors text-left"
                          >
                            <div
                              className={`w-3.5 h-3.5 rounded flex items-center justify-center shrink-0 border ${
                                checked ? "bg-emerald-600 border-emerald-600" : "border-border"
                              }`}
                            />
                            <span className="text-xs text-foreground truncate">{key}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPickerColumn(null)}
                      className="flex-1 px-3 py-1.5 rounded-lg text-xs text-muted-foreground hover:bg-muted transition-colors"
                    >
                      Retour
                    </button>
                    <button
                      onClick={applyFilter}
                      className="flex-1 px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-500 transition-colors"
                    >
                      Appliquer
                    </button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {filters.length > 0 && (
        <button
          onClick={() => onChange([])}
          className="text-xs text-muted-foreground hover:text-muted-foreground transition-colors ml-1"
        >
          Tout effacer
        </button>
      )}
    </div>
  );
}
