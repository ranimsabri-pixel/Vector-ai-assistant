"use client";

import type { HeatmapData } from "@/lib/dashboards";

// Interpole entre le fond zinc et l'emerald selon l'intensite (0-1)
function cellColor(ratio: number): string {
  const r = Math.round(24 + ratio * (16 - 24));
  const g = Math.round(24 + ratio * (185 - 24));
  const b = Math.round(27 + ratio * (129 - 27));
  return `rgb(${r}, ${g}, ${b})`;
}

export function HeatmapWidget({ data }: { data: HeatmapData }) {
  const range = data.max - data.min || 1;

  return (
    <div className="h-full overflow-auto">
      <table className="w-full text-[11px] border-separate border-spacing-0.5">
        <thead>
          <tr>
            <th className="p-1" />
            {data.cols.map((col) => (
              <th key={col} className="p-1 text-muted-foreground font-medium whitespace-nowrap">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, i) => (
            <tr key={row}>
              <td className="p-1 text-muted-foreground font-medium whitespace-nowrap text-right pr-2">
                {row}
              </td>
              {data.values[i].map((v, j) => {
                const ratio = (v - data.min) / range;
                return (
                  <td
                    key={j}
                    className="p-2 text-center text-white font-medium rounded"
                    style={{ backgroundColor: cellColor(ratio) }}
                    title={`${row} / ${data.cols[j]} : ${v}`}
                  >
                    {v.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
