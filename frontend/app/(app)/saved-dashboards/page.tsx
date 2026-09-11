"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import {
  ArrowLeft,
  Download,
  FileText,
  LayoutGrid,
  Loader2,
  Plus,
  Sheet,
  Trash2,
} from "lucide-react";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { SortableContext, arrayMove, rectSortingStrategy } from "@dnd-kit/sortable";

import {
  addWidget,
  decodeFiltersParam,
  deleteSavedDashboard,
  deleteWidget,
  encodeFiltersParam,
  exportDashboardCsv,
  getDashboardData,
  getSavedDashboard,
  reorderWidgets,
  updateSavedDashboard,
  type DashboardFilter,
  type DashboardWidget,
  type SavedDashboardDetail,
  type WidgetData,
} from "@/lib/dashboards";
import { getDatasetColumns, type DatasetColumn } from "@/lib/datasets";
import { downloadBlob, exportElementAsPdf } from "@/lib/export";
import { useAuthStore } from "@/lib/store/auth";
import { useConfirm } from "@/lib/hooks/use-confirm";
import { ConfirmDialog } from "@/components/confirm_dialog";
import { EmptyState } from "@/components/empty_state";
import { FilterBar } from "@/components/filter_bar";
import { WidgetFormModal } from "@/components/widget_form_modal";
import { SortableWidgetCard } from "@/components/widgets/sortable_widget_card";

export default function SavedDashboardEditPage() {
  return (
    <Suspense
      fallback={
        <div className="h-full flex items-center justify-center">
          <Loader2 size={28} className="animate-spin text-emerald-400" />
        </div>
      }
    >
      <SavedDashboardEditPageInner />
    </Suspense>
  );
}

function SavedDashboardEditPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const dashboardId = searchParams.get("id") ?? "";
  const token = useAuthStore((s) => s.token);
  const { confirm, dialogProps } = useConfirm();

  const [dashboard, setDashboard] = useState<SavedDashboardDetail | null>(null);
  const [columns, setColumns] = useState<DatasetColumn[]>([]);
  const [widgetData, setWidgetData] = useState<Record<string, WidgetData>>({});
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<DashboardFilter[]>(() =>
    decodeFiltersParam(searchParams.get("f")),
  );

  const [titleDraft, setTitleDraft] = useState("");
  const [editingTitle, setEditingTitle] = useState(false);

  const [formOpen, setFormOpen] = useState(false);
  const [editingWidget, setEditingWidget] = useState<DashboardWidget | null>(null);

  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const gridRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    if (!token || !dashboardId) return;
    setLoading(true);
    try {
      const detail = await getSavedDashboard(token, dashboardId);
      setDashboard(detail);
      setTitleDraft(detail.name);
      const cols = await getDatasetColumns(token, detail.dataset_id);
      setColumns(cols);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }, [token, dashboardId]);

  useEffect(() => {
    load();
  }, [load]);

  const refreshWidgetData = useCallback(
    async (id: string, currentFilters: DashboardFilter[]) => {
      if (!token) return;
      try {
        const data = await getDashboardData(token, id, currentFilters);
        setWidgetData(data);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Erreur de chargement des données");
      }
    },
    [token],
  );

  useEffect(() => {
    if (!dashboard) return;
    refreshWidgetData(dashboard.id, filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dashboard?.id, filters]);

  // Persiste les filtres actifs dans l'URL (lien partageable), sans
  // déclencher de navigation Next.js.
  useEffect(() => {
    const encoded = encodeFiltersParam(filters);
    const url = new URL(window.location.href);
    if (encoded) url.searchParams.set("f", encoded);
    else url.searchParams.delete("f");
    window.history.replaceState({}, "", url.toString());
  }, [filters]);

  async function handleRename() {
    setEditingTitle(false);
    const trimmed = titleDraft.trim();
    if (!token || !dashboard || !trimmed || trimmed === dashboard.name) {
      setTitleDraft(dashboard?.name ?? "");
      return;
    }
    try {
      const updated = await updateSavedDashboard(token, dashboard.id, { name: trimmed });
      setDashboard(updated);
      toast.success("Nom mis à jour");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de renommage");
      setTitleDraft(dashboard.name);
    }
  }

  async function handleDeleteDashboard() {
    if (!token || !dashboard) return;
    const ok = await confirm({
      title: `Supprimer "${dashboard.name}" ?`,
      description: "Ce tableau de bord et tous ses widgets seront supprimés définitivement.",
      confirmLabel: "Supprimer",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await deleteSavedDashboard(token, dashboard.id);
      toast.success("Tableau de bord supprimé");
      router.push("/dashboards");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de suppression");
    }
  }

  async function handleDeleteWidget(widget: DashboardWidget) {
    if (!token || !dashboard) return;
    const ok = await confirm({
      title: `Supprimer le widget "${widget.title}" ?`,
      description: "Cette action est irréversible.",
      confirmLabel: "Supprimer",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await deleteWidget(token, dashboard.id, widget.id);
      setDashboard((prev) =>
        prev ? { ...prev, widgets: prev.widgets.filter((w) => w.id !== widget.id) } : prev,
      );
      toast.success("Widget supprimé");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de suppression");
    }
  }

  async function handleDuplicateWidget(widget: DashboardWidget) {
    if (!token || !dashboard) return;
    try {
      const created = await addWidget(token, dashboard.id, {
        widget_type: widget.widget_type,
        title: widget.title + " (copie)",
        config: widget.config,
        position: dashboard.widgets.length,
      });
      setDashboard((prev) => (prev ? { ...prev, widgets: [...prev.widgets, created] } : prev));
      await refreshWidgetData(dashboard.id, filters);
      toast.success("Widget dupliqué");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de duplication");
    }
  }

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!token || !dashboard || !over || active.id === over.id) return;

    const oldIndex = dashboard.widgets.findIndex((w) => w.id === active.id);
    const newIndex = dashboard.widgets.findIndex((w) => w.id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;

    const reordered = arrayMove(dashboard.widgets, oldIndex, newIndex);
    setDashboard((prev) => (prev ? { ...prev, widgets: reordered } : prev));

    try {
      await reorderWidgets(token, dashboard.id, reordered.map((w) => w.id));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de réorganisation");
      load();
    }
  }

  function openCreateForm() {
    setEditingWidget(null);
    setFormOpen(true);
  }

  function openEditForm(widget: DashboardWidget) {
    setEditingWidget(widget);
    setFormOpen(true);
  }

  async function handleWidgetSaved(widget: DashboardWidget) {
    if (!dashboard || !token) return;
    setDashboard((prev) => {
      if (!prev) return prev;
      const exists = prev.widgets.some((w) => w.id === widget.id);
      return {
        ...prev,
        widgets: exists
          ? prev.widgets.map((w) => (w.id === widget.id ? widget : w))
          : [...prev.widgets, widget],
      };
    });
    await refreshWidgetData(dashboard.id, filters);
  }

  async function handleExportPdf() {
    if (!gridRef.current || !dashboard) return;
    setExportMenuOpen(false);
    setExporting(true);
    try {
      await exportElementAsPdf(gridRef.current, `${dashboard.name}.pdf`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur d'export PDF");
    } finally {
      setExporting(false);
    }
  }

  async function handleExportCsv() {
    if (!token || !dashboard) return;
    setExportMenuOpen(false);
    setExporting(true);
    try {
      const { blob, filename } = await exportDashboardCsv(token, dashboard.id, filters);
      downloadBlob(blob, filename);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur d'export CSV");
    } finally {
      setExporting(false);
    }
  }

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 size={28} className="animate-spin text-emerald-400" />
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-sm text-muted-foreground">Tableau de bord introuvable</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="max-w-6xl mx-auto px-8 py-10">
        <button
          onClick={() => router.push("/dashboards")}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-4"
        >
          <ArrowLeft size={13} />
          Retour aux dashboards
        </button>

        <div className="flex items-center justify-between mb-2 flex-wrap gap-3">
          {editingTitle ? (
            <input
              autoFocus
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={handleRename}
              onKeyDown={(e) => {
                if (e.key === "Enter") e.currentTarget.blur();
                if (e.key === "Escape") {
                  setTitleDraft(dashboard.name);
                  setEditingTitle(false);
                }
              }}
              className="text-2xl font-bold bg-transparent border-b border-emerald-500/60 text-foreground focus:outline-none"
            />
          ) : (
            <h1
              onClick={() => setEditingTitle(true)}
              className="text-2xl font-bold text-foreground cursor-text hover:opacity-80 transition-opacity"
              title="Cliquer pour renommer"
            >
              {dashboard.name}
            </h1>
          )}

          <div className="flex items-center gap-2">
            <button
              onClick={openCreateForm}
              className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm font-medium text-white flex items-center gap-2 transition-colors"
            >
              <Plus size={15} />
              Ajouter widget
            </button>
            <div className="relative">
              <button
                onClick={() => setExportMenuOpen((o) => !o)}
                disabled={exporting}
                title="Exporter"
                className="p-2 bg-card hover:bg-muted border border-border rounded-lg text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
              >
                {exporting ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Download size={15} />
                )}
              </button>
              {exportMenuOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setExportMenuOpen(false)} />
                  <div className="absolute z-50 top-full right-0 mt-2 w-56 bg-card border border-border rounded-xl shadow-2xl overflow-hidden">
                    <button
                      onClick={handleExportPdf}
                      className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-xs text-foreground hover:bg-muted transition-colors text-left"
                    >
                      <FileText size={14} className="text-muted-foreground" />
                      Exporter en PDF
                    </button>
                    <button
                      onClick={handleExportCsv}
                      className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-xs text-foreground hover:bg-muted transition-colors text-left"
                    >
                      <Sheet size={14} className="text-muted-foreground" />
                      Exporter les données (CSV)
                    </button>
                  </div>
                </>
              )}
            </div>
            <button
              onClick={handleDeleteDashboard}
              className="p-2 hover:bg-red-600/10 border border-border hover:border-red-900 rounded-lg text-muted-foreground hover:text-red-400 transition-colors"
              title="Supprimer le tableau de bord"
            >
              <Trash2 size={15} />
            </button>
          </div>
        </div>

        <p className="text-sm text-muted-foreground mb-4">
          Dataset : {dashboard.dataset_name}
          {dashboard.description && <> · {dashboard.description}</>}
        </p>

        {columns.length > 0 && (
          <FilterBar
            datasetId={dashboard.dataset_id}
            columns={columns}
            filters={filters}
            onChange={setFilters}
          />
        )}

        {dashboard.widgets.length === 0 ? (
          <EmptyState
            icon={LayoutGrid}
            title="Aucun widget pour le moment"
            description="Ajoute un premier widget (KPI, graphique, tableau) pour commencer à visualiser ce dataset."
            action={
              <button
                onClick={openCreateForm}
                className="px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 rounded-lg text-sm font-medium text-white transition-colors shadow-lg shadow-emerald-900/30"
              >
                Ajouter un widget
              </button>
            }
          />
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext
              items={dashboard.widgets.map((w) => w.id)}
              strategy={rectSortingStrategy}
            >
              <div ref={gridRef} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pb-8">
                {dashboard.widgets.map((widget) => (
                  <SortableWidgetCard
                    key={widget.id}
                    widget={widget}
                    data={widgetData[widget.id]}
                    onEdit={() => openEditForm(widget)}
                    onDuplicate={() => handleDuplicateWidget(widget)}
                    onDelete={() => handleDeleteWidget(widget)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>

      {dashboard && (
        <WidgetFormModal
          open={formOpen}
          onClose={() => setFormOpen(false)}
          dashboardId={dashboard.id}
          datasetId={dashboard.dataset_id}
          widget={editingWidget}
          onSaved={handleWidgetSaved}
        />
      )}

      <ConfirmDialog {...dialogProps} />
    </div>
  );
}
