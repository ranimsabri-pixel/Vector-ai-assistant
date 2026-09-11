"use client";

import { TrendingDown, TrendingUp } from "lucide-react";
import type { KpiData } from "@/lib/dashboards";

function formatValue(v: number): string {
  if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (Math.abs(v) >= 1_000) return (v / 1_000).toFixed(1) + "k";
  return v.toLocaleString("fr-FR", { maximumFractionDigits: 2 });
}

export function KpiWidget({ data }: { data: KpiData }) {
  const isPositiveTrend = data.trend !== null && data.trend >= 0;

  return (
    <div className="h-full flex flex-col justify-center items-start px-2">
      <p className="text-3xl font-bold text-foreground tracking-tight">
        {formatValue(data.value)}
      </p>
      {data.trend !== null && (
        <div
          className={`flex items-center gap-1 mt-2 text-xs font-medium ${
            isPositiveTrend ? "text-emerald-400" : "text-red-400"
          }`}
        >
          {isPositiveTrend ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
          {Math.abs(data.trend).toFixed(1)}%
        </div>
      )}
    </div>
  );
}
