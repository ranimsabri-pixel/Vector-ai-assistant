"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART_COLORS, type HistogramData } from "@/lib/dashboards";
import { useChartTheme } from "@/lib/chart-theme";

export function HistogramWidget({ data }: { data: HistogramData }) {
  const chartTheme = useChartTheme();
  const tooltipStyle = {
    backgroundColor: chartTheme.tooltipBg,
    border: `1px solid ${chartTheme.axisColor}`,
    borderRadius: 8,
    fontSize: 12,
    color: chartTheme.foreground,
  };
  const rows = data.bins.map((bin, i) => ({ bin, count: data.counts[i] }));
  const hasStats = data.mean !== null || data.median !== null;

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.gridColor} />
            <XAxis dataKey="bin" stroke={chartTheme.mutedForeground} fontSize={10} interval="preserveStartEnd" />
            <YAxis stroke={chartTheme.mutedForeground} fontSize={11} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: chartTheme.gridColor + "55" }} />
            <Bar dataKey="count" fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {hasStats && (
        <div className="flex items-center gap-4 text-[11px] text-muted-foreground pt-2 shrink-0">
          {data.mean !== null && (
            <span>
              Moyenne :{" "}
              <span className="text-foreground font-medium">
                {data.mean.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}
              </span>
            </span>
          )}
          {data.median !== null && (
            <span>
              Médiane :{" "}
              <span className="text-foreground font-medium">
                {data.median.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}
              </span>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
