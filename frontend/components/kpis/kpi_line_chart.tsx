"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { TrendingUp } from "lucide-react";

import { type KPISpec, type KPIResult } from "@/lib/datasets";
import { useChartTheme } from "@/lib/chart-theme";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

interface KpiLineChartProps {
  spec: KPISpec;
  result: KPIResult;
}

type TrendPoint = { label: string; value: number };

export function KpiLineChart({ spec, result }: KpiLineChartProps) {
  const [mounted, setMounted] = useState(false);
  const chartTheme = useChartTheme();

  useEffect(() => {
    setMounted(true);
  }, []);

  const points = (result.metadata?.points as TrendPoint[]) || [];

  if (points.length === 0) {
    return (
      <div className="bg-card/50 border border-border rounded-xl p-6">
        <p className="text-sm text-muted-foreground">Aucune donnée temporelle à afficher</p>
      </div>
    );
  }

  const categories = points.map((p) => {
    const d = new Date(p.label);
    return d.toLocaleDateString("fr-FR", { month: "short", year: "2-digit" });
  });
  const values = points.map((p) => p.value);

  const options = {
    chart: {
      id: "line-" + spec.id,
      type: "area" as const,
      background: "transparent",
      toolbar: { show: false },
      animations: { enabled: false }, // ← désactivé pour éviter le crash
      zoom: { enabled: false },
      fontFamily: "inherit",
    },
    theme: { mode: chartTheme.mode },
    colors: ["#06b6d4"],
    stroke: {
      curve: "smooth" as const,
      width: 2,
    },
    fill: {
      type: "gradient",
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.4,
        opacityTo: 0.05,
        stops: [0, 100],
      },
    },
    dataLabels: { enabled: false },
    markers: {
      size: 4,
      colors: ["#06b6d4"],
      strokeColors: "#0e7490",
      strokeWidth: 2,
      hover: { size: 6 },
    },
    xaxis: {
      categories,
      labels: { style: { colors: chartTheme.labelColor, fontSize: "11px" } },
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
      x: { show: true },
      y: {
        formatter: (val: number) => {
          const formatted = new Intl.NumberFormat("fr-FR").format(val);
          return formatted + (spec.unit ? " " + spec.unit : "");
        },
      },
    },
  };

  const series = [{ name: spec.title, data: values }];

  const first = values[0] || 0;
  const last = values[values.length - 1] || 0;
  const evolution =
    first !== 0 ? Math.round(((last - first) / Math.abs(first)) * 100) : 0;
  const isUp = evolution >= 0;

  return (
    <div className="bg-card/50 border border-border rounded-xl p-5 hover:border-border transition-colors">
      <div className="flex items-start gap-3 mb-4">
        <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
          <TrendingUp size={18} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-foreground mb-0.5">
            {spec.title}
          </h3>
          <p className="text-xs text-muted-foreground line-clamp-2">{spec.description}</p>
        </div>
      </div>

      <div className="-mx-2 min-h-[240px]">
        {mounted ? (
          <Chart options={options} series={series} type="area" height={240} />
        ) : (
          <div className="h-[240px] flex items-center justify-center">
            <p className="text-xs text-muted-foreground">Chargement du graphique...</p>
          </div>
        )}
      </div>

      <div className="mt-3 pt-3 border-t border-border/50 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">
          {points.length} point{points.length > 1 ? "s" : ""} ·{" "}
          {spec.granularity || "month"}
        </span>
        <span
          className={
            "font-medium flex items-center gap-1 " +
            (isUp ? "text-emerald-400" : "text-red-400")
          }
        >
          {isUp ? "↑" : "↓"} {Math.abs(evolution)}%
        </span>
      </div>
    </div>
  );
}