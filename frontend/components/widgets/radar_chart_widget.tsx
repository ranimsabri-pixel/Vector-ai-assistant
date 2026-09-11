"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import { CHART_COLORS, type RadarData } from "@/lib/dashboards";
import { useChartTheme } from "@/lib/chart-theme";

export function RadarChartWidget({ data }: { data: RadarData }) {
  const chartTheme = useChartTheme();
  const tooltipStyle = {
    backgroundColor: chartTheme.tooltipBg,
    border: `1px solid ${chartTheme.axisColor}`,
    borderRadius: 8,
    fontSize: 12,
    color: chartTheme.foreground,
  };
  const rows = data.axes.map((axis, i) => {
    const row: Record<string, string | number> = { axis };
    for (const s of data.series) row[s.name] = s.values[i];
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height="100%">
      <RadarChart data={rows}>
        <PolarGrid stroke={chartTheme.gridColor} />
        <PolarAngleAxis dataKey="axis" stroke={chartTheme.labelColor} fontSize={11} />
        <PolarRadiusAxis stroke={chartTheme.axisColor} fontSize={9} />
        <Tooltip contentStyle={tooltipStyle} />
        {data.series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
        {data.series.map((s, i) => (
          <Radar
            key={s.name}
            name={s.name}
            dataKey={s.name}
            stroke={CHART_COLORS[i % CHART_COLORS.length]}
            fill={CHART_COLORS[i % CHART_COLORS.length]}
            fillOpacity={0.25}
          />
        ))}
      </RadarChart>
    </ResponsiveContainer>
  );
}
