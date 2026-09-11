"use client";

import { useEffect, useState } from "react";
import { Check, MoreVertical, Pencil, RotateCcw, Trash2 } from "lucide-react";

import type { ColumnDetectedType, ColumnPreview, FilePreview } from "@/lib/file_preview";

// Colonne de preview enrichie de l'etat d'edition (nom original conserve
// pour construire les column_overrides, flag deleted pour la suppression).
export type EditableColumnPreview = ColumnPreview & {
  original_name: string;
  deleted: boolean;
};

const TYPE_LABELS: Record<ColumnDetectedType, string> = {
  numeric: "Numérique",
  categorical: "Catégorielle",
  datetime: "Date",
  boolean: "Booléen",
  text: "Texte",
};

const TYPE_BADGE_CLASSES: Record<ColumnDetectedType, string> = {
  numeric: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  categorical: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  datetime: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  boolean: "bg-purple-500/10 text-purple-400 border-purple-500/30",
  text: "bg-muted text-muted-foreground border-border",
};

const TYPE_OPTIONS: ColumnDetectedType[] = [
  "numeric",
  "categorical",
  "datetime",
  "boolean",
  "text",
];

type DatasetPreviewTableProps = {
  preview: FilePreview;
  editable: boolean;
  onColumnsChange?: (columns: EditableColumnPreview[]) => void;
};

export function DatasetPreviewTable({
  preview,
  editable,
  onColumnsChange,
}: DatasetPreviewTableProps) {
  const [columns, setColumns] = useState<EditableColumnPreview[]>(() =>
    preview.columns.map((c) => ({ ...c, original_name: c.name, deleted: false })),
  );
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [nameDraft, setNameDraft] = useState("");
  const [menuOpenIndex, setMenuOpenIndex] = useState<number | null>(null);
  const [typeMenuOpenIndex, setTypeMenuOpenIndex] = useState<number | null>(null);

  useEffect(() => {
    setColumns(preview.columns.map((c) => ({ ...c, original_name: c.name, deleted: false })));
  }, [preview]);

  function updateColumns(next: EditableColumnPreview[]) {
    setColumns(next);
    onColumnsChange?.(next);
  }

  function startEditName(index: number) {
    setEditingIndex(index);
    setNameDraft(columns[index].name);
  }

  function commitEditName(index: number) {
    const trimmed = nameDraft.trim();
    setEditingIndex(null);
    if (!trimmed || trimmed === columns[index].name) return;
    updateColumns(columns.map((c, i) => (i === index ? { ...c, name: trimmed } : c)));
  }

  function changeType(index: number, type: ColumnDetectedType) {
    setTypeMenuOpenIndex(null);
    setMenuOpenIndex(null);
    updateColumns(columns.map((c, i) => (i === index ? { ...c, detected_type: type } : c)));
  }

  function toggleDeleted(index: number) {
    setMenuOpenIndex(null);
    setTypeMenuOpenIndex(null);
    updateColumns(columns.map((c, i) => (i === index ? { ...c, deleted: !c.deleted } : c)));
  }

  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <div className="overflow-x-auto max-h-96">
        <table className="w-full text-xs border-collapse">
          <thead className="sticky top-0 z-10 bg-card">
            <tr>
              {columns.map((col, i) => (
                <th
                  key={i}
                  className={`text-left px-3 py-2.5 border-b border-border whitespace-nowrap min-w-[140px] align-top ${
                    col.deleted ? "opacity-40" : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 group/col">
                    <div className="flex-1 min-w-0">
                      {editingIndex === i ? (
                        <input
                          autoFocus
                          value={nameDraft}
                          onChange={(e) => setNameDraft(e.target.value)}
                          onBlur={() => commitEditName(i)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              e.currentTarget.blur();
                            }
                            if (e.key === "Escape") setEditingIndex(null);
                          }}
                          className="w-full px-1.5 py-0.5 bg-background border border-emerald-500/60 rounded text-xs text-foreground focus:outline-none"
                        />
                      ) : (
                        <button
                          type="button"
                          onClick={() => editable && !col.deleted && startEditName(i)}
                          disabled={!editable || col.deleted}
                          title={editable ? "Cliquer pour renommer" : undefined}
                          className={`font-semibold truncate block text-left ${
                            col.deleted ? "line-through text-red-400" : "text-foreground"
                          } ${editable && !col.deleted ? "hover:text-emerald-400" : ""}`}
                        >
                          {col.name}
                        </button>
                      )}
                      <span
                        className={`inline-block mt-1 px-1.5 py-0.5 rounded text-[9px] font-medium uppercase border ${TYPE_BADGE_CLASSES[col.detected_type]}`}
                      >
                        {TYPE_LABELS[col.detected_type]}
                      </span>
                    </div>

                    {editable && (
                      <div className="relative shrink-0 opacity-0 group-hover/col:opacity-100 transition-opacity">
                        <button
                          type="button"
                          onClick={() => setMenuOpenIndex(menuOpenIndex === i ? null : i)}
                          className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
                        >
                          <MoreVertical size={13} />
                        </button>
                        {menuOpenIndex === i && (
                          <>
                            <div
                              className="fixed inset-0 z-40"
                              onClick={() => {
                                setMenuOpenIndex(null);
                                setTypeMenuOpenIndex(null);
                              }}
                            />
                            <div className="absolute z-50 top-full right-0 mt-1 w-44 bg-card border border-border rounded-lg shadow-2xl overflow-visible normal-case">
                              {col.deleted ? (
                                <button
                                  type="button"
                                  onClick={() => toggleDeleted(i)}
                                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-foreground hover:bg-muted transition-colors text-left"
                                >
                                  <RotateCcw size={12} className="text-muted-foreground" />
                                  Restaurer
                                </button>
                              ) : (
                                <>
                                  <div className="relative">
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setTypeMenuOpenIndex(typeMenuOpenIndex === i ? null : i)
                                      }
                                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-foreground hover:bg-muted transition-colors text-left"
                                    >
                                      <Pencil size={12} className="text-muted-foreground" />
                                      Changer le type
                                    </button>
                                    {typeMenuOpenIndex === i && (
                                      <div className="absolute left-full top-0 ml-1 w-36 bg-card border border-border rounded-lg shadow-2xl overflow-hidden">
                                        {TYPE_OPTIONS.map((t) => (
                                          <button
                                            type="button"
                                            key={t}
                                            onClick={() => changeType(i, t)}
                                            className="w-full flex items-center justify-between px-3 py-2 text-xs text-foreground hover:bg-muted transition-colors text-left"
                                          >
                                            {TYPE_LABELS[t]}
                                            {col.detected_type === t && (
                                              <Check size={12} className="text-emerald-400" />
                                            )}
                                          </button>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => toggleDeleted(i)}
                                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-400 hover:bg-red-950/40 transition-colors text-left"
                                  >
                                    <Trash2 size={12} />
                                    Supprimer cette colonne
                                  </button>
                                </>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, rowIndex) => (
              <tr key={rowIndex} className={rowIndex % 2 === 1 ? "bg-background/50" : ""}>
                {columns.map((col, colIndex) => (
                  <td
                    key={colIndex}
                    className={`px-3 py-2 text-muted-foreground whitespace-nowrap border-b border-border/60 ${
                      col.deleted ? "opacity-40 line-through" : ""
                    }`}
                  >
                    {row[colIndex] || <span className="text-muted-foreground">—</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-3 py-2 bg-background/50 border-t border-border text-[11px] text-muted-foreground">
        Aperçu des 10 premières lignes · ~
        {preview.total_rows_estimated.toLocaleString("fr-FR")} lignes estimées au total
      </div>
    </div>
  );
}
