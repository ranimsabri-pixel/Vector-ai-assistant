"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { BarChart3 } from "lucide-react";

import { type KPISpec, type KPIResult } from "@/lib/datasets";
import { useChartTheme } from "@/lib/chart-theme";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

interface KpiBarChartProps {
  spec: KPISpec;
  result: KPIResult;
}

export function KpiBarChart({ spec, result }: KpiBarChartProps) {
  const [mounted, setMounted] = useState(false);
  const chartTheme = useChartTheme();

  useEffect(() => {
    setMounted(true);
  }, []);

  const breakdown = (result.metadata?.breakdown as Record<string, number>) || {};
  const categories = Object.keys(breakdown);
  const values = Object.values(breakdown);

  if (categories.length === 0) {
    return (
      <div className="bg-card/50 border border-border rounded-xl p-6">
        <p className="text-sm text-muted-foreground">Aucune donnée à afficher</p>
      </div>
    );
  }

  const options = {
    chart: {
      id: "bar-" + spec.id,
      type: "bar" as const,
      background: "transparent",
      toolbar: { show: false },
      animations: { enabled: false }, // ← désactivé pour éviter le crash
      fontFamily: "inherit",
    },
    theme: { mode: chartTheme.mode },
    colors: [chartTheme.primary],
    plotOptions: {
      bar: {
        borderRadius: 6,
        horizontal: false,
        columnWidth: "60%",
      },
    },
    dataLabels: { enabled: false },
    xaxis: {
      categories,
      labels: {
        style: { colors: chartTheme.labelColor, fontSize: "11px" },
        rotate: categories.some((c) => c.length > 8) ? -30 : 0,
      },
      axisBorder: { color: chartTheme.axisColor },
      axisTicks: { color: chartTheme.axisColor },
    },
    yaxis: {
      labels: {
        style: { colors: chartTheme.labelColor, fontSize: "11px" },
        formatter: (val: number) => {
          if (val >= 1_000_000) return (val / 1_000_000).toFixed(1) + "M";
          if (val >= 1_000) return (val / 1_000).toFixed(1) + "k";
          return val.toFixed(0);
        },
      },
    },
    grid: {
      borderColor: chartTheme.gridColor,
      strokeDashArray: 3,
    },
    tooltip: {
      theme: chartTheme.mode,
      y: {
        formatter: (val: number) => {
          const formatted = new Intl.NumberFormat("fr-FR").format(val);
          return formatted + (spec.unit ? " " + spec.unit : "");
        },
      },
    },
  };

  const series = [{ name: spec.title, data: values }];

  return (
    <div className="bg-card/50 border border-border rounded-xl p-5 hover:border-muted-foreground/40 transition-colors">
      <div className="flex items-start gap-3 mb-4">
        <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
          <BarChart3 size={18} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-foreground mb-0.5">
            {spec.title}
          </h3>
          <p className="text-xs text-muted-foreground line-clamp-2">{spec.description}</p>
        </div>
      </div>

      <div className="-mx-2 min-h-[260px]">
        {mounted ? (
          <Chart options={options} series={series} type="bar" height={260} />
        ) : (
          <div className="h-[260px] flex items-center justify-center">
            <p className="text-xs text-muted-foreground">Chargement du graphique...</p>
          </div>
        )}
      </div>

      <div className="mt-3 pt-3 border-t border-border/50 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">
          {categories.length} catégorie{categories.length > 1 ? "s" : ""}
        </span>
        <span className="text-muted-foreground font-medium">
          Total : {result.formatted}
        </span>
      </div>
    </div>
  );
}