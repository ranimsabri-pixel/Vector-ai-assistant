"use client";

import { useRef, useState } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { toast } from "sonner";
import {
  ClipboardCopy,
  Copy,
  Download,
  GripVertical,
  Loader2,
  Pencil,
  Trash2,
} from "lucide-react";

import {
  isWidgetError,
  type DashboardWidget,
  type DataTableData,
  type KpiData,
  type WidgetData,
} from "@/lib/dashboards";
import {
  copyElementAsPngToClipboard,
  copyTextToClipboard,
  exportElementAsPng,
} from "@/lib/export";
import { WidgetRenderer, isWideWidget } from "@/components/widgets/widget_renderer";

function tableToTsv(data: DataTableData): string {
  const header = data.columns.join("\t");
  const rows = data.rows.map((row) => row.map((cell) => cell ?? "").join("\t"));
  return [header, ...rows].join("\n");
}

export function SortableWidgetCard({
  widget,
  data,
  onEdit,
  onDuplicate,
  onDelete,
}: {
  widget: DashboardWidget;
  data: WidgetData | undefined;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: widget.id,
  });
  const captureRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  async function handleDownloadPng() {
    setMenuOpen(false);
    if (!captureRef.current) return;
    setExporting(true);
    try {
      await exportElementAsPng(captureRef.current, `${widget.title}.png`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur d'export PNG");
    } finally {
      setExporting(false);
    }
  }

  async function handleCopy() {
    setMenuOpen(false);
    if (!data || isWidgetError(data)) {
      toast.error("Aucune donnée à copier");
      return;
    }
    setExporting(true);
    try {
      if (widget.widget_type === "kpi") {
        await copyTextToClipboard(String((data as KpiData).value));
        toast.success("Valeur copiée dans le presse-papiers");
      } else if (widget.widget_type === "data_table") {
        await copyTextToClipboard(tableToTsv(data as DataTableData));
        toast.success("Tableau copié dans le presse-papiers");
      } else if (captureRef.current) {
        await copyElementAsPngToClipboard(captureRef.current);
        toast.success("Image copiée dans le presse-papiers");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de copie");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`group relative bg-card/50 border border-border rounded-xl p-4 hover:border-border transition-colors flex flex-col ${
        isWideWidget(widget.widget_type) ? "md:col-span-2" : ""
      }`}
      data-min-height={widget.widget_type === "kpi" ? 120 : 280}
    >
      <div
        style={{ minHeight: widget.widget_type === "kpi" ? 120 : 280 }}
        className="flex flex-col h-full"
      >
        <div className="flex items-center justify-between mb-2 shrink-0">
          <h3 className="text-xs font-semibold text-foreground uppercase tracking-wide truncate">
            {widget.title}
          </h3>
          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            <button
              {...attributes}
              {...listeners}
              className="p-1.5 hover:bg-muted rounded text-muted-foreground hover:text-foreground cursor-grab active:cursor-grabbing touch-none"
              title="Réorganiser (glisser-déposer)"
            >
              <GripVertical size={13} />
            </button>
            <div className="relative">
              <button
                onClick={() => setMenuOpen((o) => !o)}
                disabled={exporting}
                className="p-1.5 hover:bg-muted rounded text-muted-foreground hover:text-emerald-400 transition-colors disabled:opacity-40"
                title="Exporter / copier"
              >
                {exporting ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <Download size={13} />
                )}
              </button>
              {menuOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
                  <div className="absolute z-50 top-full right-0 mt-1 w-48 bg-card border border-border rounded-lg shadow-2xl overflow-hidden">
                    <button
                      onClick={handleDownloadPng}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-foreground hover:bg-muted transition-colors text-left"
                    >
                      <Download size={12} className="text-muted-foreground" />
                      Télécharger en PNG
                    </button>
                    <button
                      onClick={handleCopy}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-foreground hover:bg-muted transition-colors text-left"
                    >
                      <ClipboardCopy size={12} className="text-muted-foreground" />
                      Copier dans le presse-papiers
                    </button>
                  </div>
                </>
              )}
            </div>
            <button
              onClick={onEdit}
              className="p-1.5 hover:bg-muted rounded text-muted-foreground hover:text-emerald-400 transition-colors"
              title="Modifier"
            >
              <Pencil size={13} />
            </button>
            <button
              onClick={onDuplicate}
              className="p-1.5 hover:bg-muted rounded text-muted-foreground hover:text-emerald-400 transition-colors"
              title="Dupliquer"
            >
              <Copy size={13} />
            </button>
            <button
              onClick={onDelete}
              className="p-1.5 hover:bg-red-600/10 rounded text-muted-foreground hover:text-red-400 transition-colors"
              title="Supprimer"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>
        <div ref={captureRef} className="flex-1 min-h-0 bg-inherit">
          <WidgetRenderer widget={widget} data={data} />
        </div>
      </div>
    </div>
  );
}
