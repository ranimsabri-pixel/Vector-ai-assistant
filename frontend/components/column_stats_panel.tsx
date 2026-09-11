"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DatasetColumn } from "@/lib/datasets";
import { useChartTheme } from "@/lib/chart-theme";

const numberFormatter = new Intl.NumberFormat("fr-FR", {
  maximumFractionDigits: 2,
});

type ColumnStatsPanelProps = {
  column: DatasetColumn;
  onReprofile?: () => void;
  reprofiling?: boolean;
};

export function ColumnStatsPanel({
  column,
  onReprofile,
  reprofiling,
}: ColumnStatsPanelProps) {
  const chartTheme = useChartTheme();
  const tooltipStyle = {
    background: chartTheme.tooltipBg,
    border: `1px solid ${chartTheme.axisColor}`,
    borderRadius: 8,
    fontSize: 12,
  };
  const tooltipLabelStyle = { color: chartTheme.foreground };
  const axisTick = { fontSize: 9, fill: chartTheme.mutedForeground };

  const hasStats =
    !!column.numeric_stats || !!column.categorical_stats || !!column.date_stats;

  if (!hasStats) {
    return (
      <div className="px-4 py-5 border-t border-border text-center">
        <p className="text-xs text-muted-foreground mb-3">
          Statistiques non disponibles pour cette colonne
        </p>
        {onReprofile && (
          <button
            type="button"
            onClick={onReprofile}
            disabled={reprofiling}
            className="px-3 py-1.5 bg-muted hover:bg-muted-foreground/10 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-xs font-medium text-foreground transition-colors"
          >
            {reprofiling ? "Reprofilage..." : "Reprofiler ce dataset"}
          </button>
        )}
      </div>
    );
  }

  if (column.dtype === "numeric" && column.numeric_stats) {
    const s = column.numeric_stats;
    const data = s.histogram_bins.map((b) => ({
      label: numberFormatter.format(b.bin_start),
      count: b.count,
    }));
    return (
      <div className="px-4 py-4 border-t border-border space-y-3">
        <div className="grid grid-cols-5 gap-2 text-center">
          <Stat label="Min" value={numberFormatter.format(s.min)} />
          <Stat label="Max" value={numberFormatter.format(s.max)} />
          <Stat label="Moyenne" value={numberFormatter.format(s.mean)} />
          <Stat label="Médiane" value={numberFormatter.format(s.median)} />
          <Stat label="Écart-type" value={numberFormatter.format(s.std_dev)} />
        </div>
        {data.length > 0 && (
          <div style={{ height: 120 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
                <XAxis
                  dataKey="label"
                  tick={axisTick}
                  axisLine={{ stroke: chartTheme.axisColor }}
                  tickLine={false}
                  interval={Math.max(0, Math.ceil(data.length / 6) - 1)}
                />
                <YAxis hide />
                <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} />
                <Bar dataKey="count" fill="#60a5fa" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    );
  }

  if (
    (column.dtype === "categorical" || column.dtype === "text") &&
    column.categorical_stats
  ) {
    const s = column.categorical_stats;
    const data = s.top_values.map((v) => ({ name: v.value, count: v.count }));
    return (
      <div className="px-4 py-4 border-t border-border space-y-2">
        <div style={{ height: Math.max(120, data.length * 26) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 4, right: 16, left: 4, bottom: 0 }}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="name"
                width={100}
                tick={{ fontSize: 10, fill: chartTheme.mutedForeground }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} />
              <Bar dataKey="count" fill="#c084fc" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-muted-foreground text-center">
          {s.total_unique.toLocaleString("fr-FR")} valeurs uniques au total
        </p>
      </div>
    );
  }

  if (column.dtype === "datetime" && column.date_stats) {
    const s = column.date_stats;
    const data = s.date_distribution.map((d) => ({
      period: d.period,
      count: d.count,
    }));
    return (
      <div className="px-4 py-4 border-t border-border space-y-2">
        <div style={{ height: 120 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
              <CartesianGrid stroke={chartTheme.gridColor} vertical={false} />
              <XAxis
                dataKey="period"
                tick={axisTick}
                axisLine={{ stroke: chartTheme.axisColor }}
                tickLine={false}
              />
              <YAxis hide />
              <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#fbbf24"
                strokeWidth={2}
                dot={{ r: 3, fill: "#fbbf24" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-muted-foreground text-center">
          du {new Date(s.min_date).toLocaleDateString("fr-FR")} au{" "}
          {new Date(s.max_date).toLocaleDateString("fr-FR")}
        </p>
      </div>
    );
  }

  return null;
}

function Stat(props: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {props.label}
      </p>
      <p className="text-sm font-semibold text-foreground">{props.value}</p>
    </div>
  );
}
