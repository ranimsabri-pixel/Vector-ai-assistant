"use client";

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { CHART_COLORS, type PieData } from "@/lib/dashboards";
import { useChartTheme } from "@/lib/chart-theme";

export function PieChartWidget({
  data,
  donut,
}: {
  data: PieData;
  donut: boolean;
}) {
  const chartTheme = useChartTheme();
  const tooltipStyle = {
    backgroundColor: chartTheme.tooltipBg,
    border: `1px solid ${chartTheme.axisColor}`,
    borderRadius: 8,
    fontSize: 12,
    color: chartTheme.foreground,
  };
  const rows = data.labels.map((label, i) => ({
    name: label,
    value: data.values[i],
    percentage: data.percentages[i],
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={rows}
          dataKey="value"
          nameKey="name"
          innerRadius={donut ? "55%" : 0}
          outerRadius="80%"
          paddingAngle={2}
        >
          {rows.map((_, i) => (
            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value, name, props) => {
            const percentage = (props?.payload as { percentage?: number } | undefined)?.percentage ?? 0;
            return [`${Number(value).toLocaleString("fr-FR")} (${percentage}%)`, name];
          }}
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
