"use client";

import { LayoutDashboard } from "lucide-react";

import { type KPISpec, type KPIResult } from "@/lib/datasets";
import { KpiCard } from "./kpi_card";

interface KpiDashboardProps {
  specs: KPISpec[];
  results: KPIResult[];
}

export function KpiDashboard({ specs, results }: KpiDashboardProps) {
  // Index des résultats par spec_id pour lookup rapide
  const resultsBySpec = results.reduce<Record<string, KPIResult>>(
    (acc, r) => {
      acc[r.spec_id] = r;
      return acc;
    },
    {}
  );

  // Sépare les KPIs en 2 groupes : grands (charts) et petits (nombres)
  const numberSpecs: KPISpec[] = [];
  const chartSpecs: KPISpec[] = [];

  for (const spec of specs) {
    const result = resultsBySpec[spec.id];
    if (!result) continue;
    if (result.chart_type === "number") {
      numberSpecs.push(spec);
    } else {
      chartSpecs.push(spec);
    }
  }

  if (specs.length === 0) {
    return null;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-2">
        <LayoutDashboard size={18} className="text-emerald-400" />
        <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Dashboard Vector ({results.length} KPIs)
        </h2>
      </div>

      {/* Bloc 1 : nombres */}
      {numberSpecs.length > 0 && (
        <section>
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-3">
            Indicateurs clés
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {numberSpecs.map((spec, i) => (
              <div
                key={spec.id}
                style={{ animationDelay: i * 50 + "ms" }}
                className="animate-in fade-in slide-in-from-bottom-2 duration-300 fill-mode-both"
              >
                <KpiCard spec={spec} result={resultsBySpec[spec.id]} />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Bloc 2 : charts */}
      {chartSpecs.length > 0 && (
        <section>
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-3">
            Analyses visuelles
          </p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {chartSpecs.map((spec, i) => (
              <div
                key={spec.id}
                style={{ animationDelay: (numberSpecs.length + i) * 50 + "ms" }}
                className="animate-in fade-in slide-in-from-bottom-2 duration-300 fill-mode-both"
              >
                <KpiCard spec={spec} result={resultsBySpec[spec.id]} />
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}