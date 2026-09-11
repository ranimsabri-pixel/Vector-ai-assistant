"use client";

import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
  Legend,
} from "recharts";
import { CHART_COLORS, type ScatterData } from "@/lib/dashboards";
import { useChartTheme } from "@/lib/chart-theme";

export function ScatterPlotWidget({ data }: { data: ScatterData }) {
  const chartTheme = useChartTheme();
  const tooltipStyle = {
    backgroundColor: chartTheme.tooltipBg,
    border: `1px solid ${chartTheme.axisColor}`,
    borderRadius: 8,
    fontSize: 12,
    color: chartTheme.foreground,
  };
  const groups = data.has_color
    ? Array.from(new Set(data.points.map((p) => p.color ?? "N/A")))
    : ["Points"];

  const series = groups.map((group) => ({
    name: group,
    points: data.has_color
      ? data.points.filter((p) => (p.color ?? "N/A") === group)
      : data.points,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ScatterChart margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.gridColor} />
        <XAxis
          type="number"
          dataKey="x"
          name={data.x_label}
          stroke={chartTheme.mutedForeground}
          fontSize={11}
        />
        <YAxis
          type="number"
          dataKey="y"
          name={data.y_label}
          stroke={chartTheme.mutedForeground}
          fontSize={11}
        />
        {data.has_size && <ZAxis type="number" dataKey="size" range={[30, 300]} />}
        <Tooltip contentStyle={tooltipStyle} cursor={{ strokeDasharray: "3 3" }} />
        {data.has_color && <Legend wrapperStyle={{ fontSize: 11 }} />}
        {series.map((s, i) => (
          <Scatter
            key={s.name}
            name={s.name}
            data={s.points}
            fill={CHART_COLORS[i % CHART_COLORS.length]}
            fillOpacity={0.7}
          />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
