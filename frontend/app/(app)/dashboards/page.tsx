"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Calendar,
  ExternalLink,
  LayoutDashboard,
  Sparkles,
  Trash2,
} from "lucide-react";

import {
  deleteDashboard,
  listDashboards,
  type Dashboard,
} from "@/lib/datasets";
import { useAuthStore } from "@/lib/store/auth";
import { useToast } from "@/lib/hooks/use-toast";
import { ToastContainer } from "@/components/toast";
import { Tabs, TabPanel } from "@/components/tabs";
import { SavedDashboardsList } from "@/components/saved_dashboards_list";
import { SavedDashboardCardSkeleton } from "@/components/skeleton";

export default function DashboardsListPage() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const { toasts, success, error: toastError, removeToast } = useToast();

  const [activeTab, setActiveTab] = useState<"generated" | "custom">("generated");
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [loading, setLoading] = useState(true);
  const [hydrated, setHydrated] = useState(false);

  async function loadDashboards() {
    if (!token) return;
    setLoading(true);
    try {
      const data = await listDashboards(token);
      console.log("📚 Dashboards reçus de l'API:", data.length, data);
      setDashboards(data);
    } catch (e) {
      console.error("❌ Erreur chargement dashboards:", e);
      toastError(e instanceof Error ? e.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }

  // Étape 1 : attendre l'hydratation du store Zustand
  useEffect(() => {
    setHydrated(true);
  }, []);

  // Étape 2 : une fois hydraté, charger les dashboards
  useEffect(() => {
    if (!hydrated) return;
    if (!token) {
      router.push("/login");
      return;
    }
    loadDashboards();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, token]);

  async function handleDelete(d: Dashboard) {
    if (!token) return;
    if (!confirm(`Supprimer le dashboard "${d.title}" ?`)) return;
    try {
      await deleteDashboard(token, d.id);
      setDashboards((prev) => prev.filter((x) => x.id !== d.id));
      success("Dashboard supprimé");
    } catch (e) {
      toastError(e instanceof Error ? e.message : "Erreur de suppression");
    }
  }

  function handleOpen(d: Dashboard) {
    window.open("/dashboard?id=" + d.dataset_id, "_blank");
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <>
      <ToastContainer toasts={toasts} onClose={removeToast} />

      <div className="h-full overflow-y-auto">
        <div className="max-w-6xl mx-auto px-8 py-10">
          <div className="mb-6">
            <p className="text-xs uppercase tracking-wider text-emerald-400 font-semibold mb-2">
              Bibliothèque Vector
            </p>
            <h1 className="text-3xl font-bold text-foreground">Mes dashboards</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Dashboards générés automatiquement ou composés à la main à partir
              de vos datasets
            </p>
          </div>

          <Tabs
            tabs={[
              { id: "generated", label: "Générés automatiquement", count: dashboards.length },
              { id: "custom", label: "Personnalisés" },
            ]}
            active={activeTab}
            onChange={setActiveTab}
          />

          <TabPanel active={activeTab} value="generated">
            <div className="flex justify-end mb-6">
              <button
                onClick={() => router.push("/datasets")}
                className="px-4 py-2 bg-card hover:bg-muted border border-border rounded-lg text-sm text-foreground flex items-center gap-2 transition-colors"
              >
                <Sparkles size={14} />
                Générer un nouveau dashboard
              </button>
            </div>

            {!hydrated || loading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <SavedDashboardCardSkeleton key={i} />
                ))}
              </div>
            ) : dashboards.length === 0 ? (
              <div className="bg-card/30 rounded-xl p-16 text-center border border-dashed border-border">
                <LayoutDashboard size={40} className="text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground text-base font-medium mb-2">
                  Aucun dashboard généré pour le moment
                </p>
                <p className="text-muted-foreground text-sm mb-6">
                  Commencez par uploader et analyser un dataset
                </p>
                <button
                  onClick={() => router.push("/datasets")}
                  className="px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 rounded-lg text-sm font-medium text-white transition-colors shadow-lg shadow-emerald-900/30"
                >
                  Aller aux datasets
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {dashboards.map((d, i) => (
                  <DashboardCard
                    key={d.id}
                    dashboard={d}
                    delay={i * 50}
                    onOpen={() => handleOpen(d)}
                    onDelete={() => handleDelete(d)}
                    formatDate={formatDate}
                  />
                ))}
              </div>
            )}
          </TabPanel>

          <TabPanel active={activeTab} value="custom">
            <SavedDashboardsList />
          </TabPanel>
        </div>
      </div>
    </>
  );
}

function DashboardCard(props: {
  dashboard: Dashboard;
  delay: number;
  onOpen: () => void;
  onDelete: () => void;
  formatDate: (iso: string | null) => string;
}) {
  const d = props.dashboard;
  const kpiCount = d.kpi_results?.length || 0;

  return (
    <div
      style={{ animationDelay: props.delay + "ms" }}
      className="bg-card/50 border border-border rounded-xl p-5 hover:border-border transition-colors animate-in fade-in slide-in-from-bottom-2 duration-300 fill-mode-both group"
    >
      <div className="flex items-start gap-3 mb-4">
        <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
          <LayoutDashboard size={18} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-foreground truncate mb-1">
            {d.title}
          </h3>
          <p className="text-xs text-muted-foreground">{kpiCount} KPIs calculés</p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-4">
        <Calendar size={12} />
        <span>Généré le {props.formatDate(d.generated_at)}</span>
      </div>

      <div className="flex gap-2">
        <button
          onClick={props.onOpen}
          className="flex-1 px-3 py-2 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 rounded-lg text-xs font-medium text-white flex items-center justify-center gap-2 transition-colors"
        >
          <ExternalLink size={13} />
          Ouvrir
        </button>
        <button
          onClick={props.onDelete}
          className="px-3 py-2 bg-card hover:bg-red-950 border border-border hover:border-red-900 rounded-lg text-xs text-muted-foreground hover:text-red-400 transition-colors"
          title="Supprimer"
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}