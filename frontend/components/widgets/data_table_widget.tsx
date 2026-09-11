"use client";

import type { DataTableData } from "@/lib/dashboards";

export function DataTableWidget({ data }: { data: DataTableData }) {
  return (
    <div className="h-full overflow-auto">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-card">
          <tr>
            {data.columns.map((col) => (
              <th
                key={col}
                className="text-left px-3 py-2 font-medium text-muted-foreground border-b border-border whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, i) => (
            <tr key={i} className="border-b border-border/60 hover:bg-muted/30">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2 text-foreground whitespace-nowrap">
                  {cell === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    String(cell)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
