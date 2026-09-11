"use client";

import type { CorrelationMatrixData } from "@/lib/dashboards";

// Echelle divergente : -1 rouge, 0 neutre zinc, +1 emerald
function cellColor(v: number): string {
  if (v >= 0) {
    const r = Math.round(39 + v * (16 - 39));
    const g = Math.round(39 + v * (185 - 39));
    const b = Math.round(42 + v * (129 - 42));
    return `rgb(${r}, ${g}, ${b})`;
  }
  const t = -v;
  const r = Math.round(39 + t * (239 - 39));
  const g = Math.round(39 + t * (68 - 39));
  const b = Math.round(42 + t * (68 - 42));
  return `rgb(${r}, ${g}, ${b})`;
}

export function CorrelationMatrixWidget({ data }: { data: CorrelationMatrixData }) {
  return (
    <div className="h-full overflow-auto">
      <table className="w-full text-[11px] border-separate border-spacing-0.5">
        <thead>
          <tr>
            <th className="p-1" />
            {data.columns.map((col) => (
              <th key={col} className="p-1 text-muted-foreground font-medium whitespace-nowrap">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.columns.map((row, i) => (
            <tr key={row}>
              <td className="p-1 text-muted-foreground font-medium whitespace-nowrap text-right pr-2">
                {row}
              </td>
              {data.matrix[i].map((v, j) => (
                <td
                  key={j}
                  className="p-2 text-center text-white font-medium rounded"
                  style={{ backgroundColor: cellColor(v) }}
                  title={`${row} / ${data.columns[j]} : ${v}`}
                >
                  {v.toFixed(2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[10px] text-muted-foreground mt-2">Méthode : {data.method}</p>
    </div>
  );
}
