"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { LayoutGrid, Plus, Trash2 } from "lucide-react";

import {
  deleteSavedDashboard,
  listSavedDashboards,
  type SavedDashboardSummary,
} from "@/lib/dashboards";
import { useAuthStore } from "@/lib/store/auth";
import { useConfirm } from "@/lib/hooks/use-confirm";
import { ConfirmDialog } from "@/components/confirm_dialog";
import { EmptyState } from "@/components/empty_state";
import { SavedDashboardListSkeleton } from "@/components/skeleton";
import { DashboardCreateModal } from "@/components/dashboard_create_modal";

export function SavedDashboardsList() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const { confirm, dialogProps } = useConfirm();

  const [dashboards, setDashboards] = useState<SavedDashboardSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);

  async function refresh() {
    if (!token) return;
    setLoading(true);
    try {
      const data = await listSavedDashboards(token);
      setDashboards(data);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (token) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleDelete(d: SavedDashboardSummary) {
    if (!token) return;

    const ok = await confirm({
      title: `Supprimer "${d.name}" ?`,
      description:
        "Ce tableau de bord et tous ses widgets seront supprimés définitivement. Le dataset source reste intact.",
      confirmLabel: "Supprimer",
      variant: "danger",
    });

    if (!ok) return;

    try {
      await deleteSavedDashboard(token, d.id);
      setDashboards((prev) => prev.filter((x) => x.id !== d.id));
      toast.success(`Tableau de bord "${d.name}" supprimé`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de suppression");
    }
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  return (
    <>
      <button
        onClick={() => setCreateOpen(true)}
        className="mb-4 flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm font-medium text-white transition-colors"
      >
        <Plus size={16} />
        Créer un tableau de bord
      </button>

      {loading && dashboards.length === 0 ? (
        <SavedDashboardListSkeleton count={6} />
      ) : dashboards.length === 0 ? (
        <EmptyState
          icon={LayoutGrid}
          title="Aucun tableau de bord personnalisé pour le moment"
          description="Crée ton premier tableau de bord en choisissant un dataset, puis ajoute des widgets (KPI, graphiques, tableaux) pour visualiser tes données à ta façon."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {dashboards.map((d) => (
            <div
              key={d.id}
              className="group bg-card/50 border border-border rounded-xl p-5 hover:border-border transition-colors cursor-pointer"
              onClick={() => router.push(`/saved-dashboards?id=${d.id}`)}
            >
              <div className="flex items-start gap-3 mb-4">
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 shrink-0">
                  <LayoutGrid size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-foreground truncate mb-1">
                    {d.name}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {d.widget_count} widget{d.widget_count > 1 ? "s" : ""} ·{" "}
                    {d.dataset_name}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(d);
                  }}
                  className="p-1.5 opacity-0 group-hover:opacity-100 hover:bg-red-600/10 rounded-lg text-muted-foreground hover:text-red-400 transition-all shrink-0"
                  title="Supprimer"
                >
                  <Trash2 size={14} />
                </button>
              </div>

              {d.description && (
                <p className="text-xs text-muted-foreground line-clamp-2 mb-3">
                  {d.description}
                </p>
              )}

              <p className="text-[11px] text-muted-foreground">
                Mis à jour le {formatDate(d.updated_at)}
              </p>
            </div>
          ))}
        </div>
      )}

      <DashboardCreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(dashboard) => router.push(`/saved-dashboards?id=${dashboard.id}`)}
      />

      <ConfirmDialog {...dialogProps} />
    </>
  );
}
