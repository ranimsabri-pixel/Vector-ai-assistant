"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART_COLORS, type BarLineData } from "@/lib/dashboards";
import { useChartTheme } from "@/lib/chart-theme";

export function BarLineChartWidget({
  data,
  kind,
}: {
  data: BarLineData;
  kind: "bar_chart" | "line_chart";
}) {
  const chartTheme = useChartTheme();
  const tooltipStyle = {
    backgroundColor: chartTheme.tooltipBg,
    border: `1px solid ${chartTheme.axisColor}`,
    borderRadius: 8,
    fontSize: 12,
    color: chartTheme.foreground,
  };

  const rows = data.labels.map((label, i) => {
    const row: Record<string, string | number> = { label };
    if (data.series) {
      for (const s of data.series) row[s.name] = s.data[i];
    } else if (data.values) {
      row.value = data.values[i];
    }
    return row;
  });

  const seriesKeys = data.series ? data.series.map((s) => s.name) : ["value"];
  const Chart = kind === "line_chart" ? LineChart : BarChart;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <Chart data={rows} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.gridColor} />
        <XAxis dataKey="label" stroke={chartTheme.mutedForeground} fontSize={11} />
        <YAxis stroke={chartTheme.mutedForeground} fontSize={11} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: chartTheme.gridColor + "55" }} />
        {seriesKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
        {seriesKeys.map((key, i) =>
          kind === "line_chart" ? (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={CHART_COLORS[i % CHART_COLORS.length]}
              strokeWidth={2}
              dot={false}
            />
          ) : (
            <Bar
              key={key}
              dataKey={key}
              fill={CHART_COLORS[i % CHART_COLORS.length]}
              radius={[4, 4, 0, 0]}
            />
          ),
        )}
      </Chart>
    </ResponsiveContainer>
  );
}
