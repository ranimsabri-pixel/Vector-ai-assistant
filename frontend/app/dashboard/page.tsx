"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Loader2,
  RefreshCw,
  Database,
  LogOut,
  Link2,
  Check,
} from "lucide-react";

import {
  calculateAllKpis,
  generateAdvancedKpis,
  generateAutoKpis,
  getDataset,
  saveDashboard,
  type DatasetDetail,
  type KPIResult,
} from "@/lib/datasets";
import { useAuthStore } from "@/lib/store/auth";
import { useToast } from "@/lib/hooks/use-toast";
import { ToastContainer } from "@/components/toast";
import { KpiDashboard } from "@/components/kpis/kpi_dashboard";
import { ExportButton } from "@/components/kpis/export_button";
import { KpiDashboardSkeleton } from "@/components/kpis/kpi_skeleton";

export default function StandaloneDashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-background flex items-center justify-center">
          <Loader2 size={40} className="animate-spin text-emerald-400" />
        </div>
      }
    >
      <StandaloneDashboardPageInner />
    </Suspense>
  );
}

function StandaloneDashboardPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const { toasts, success, error: toastError, removeToast } = useToast();
  const id = searchParams.get("id") ?? "";

  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [kpiResults, setKpiResults] = useState<KPIResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  /**
   * Sauvegarde du dashboard en BDD. Erreurs RENDUES VISIBLES via toast
   * pour qu'on sache pourquoi un dashboard n'apparaît pas dans /dashboards.
   */
  async function persistDashboard(
    datasetDetail: DatasetDetail,
    results: KPIResult[]
  ): Promise<boolean> {
    if (!token) return false;
    if (!datasetDetail.auto_kpis || results.length === 0) {
      console.warn("Sauvegarde skippée : pas de KPIs à sauvegarder");
      return false;
    }
    try {
      const saved = await saveDashboard(token, {
        dataset_id: id,
        title: datasetDetail.name + " — Dashboard",
        kpi_specs: datasetDetail.auto_kpis.specs,
        kpi_results: results,
      });
      console.log("✅ Dashboard sauvegardé en BDD, id:", saved.id);
      return true;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "erreur inconnue";
      console.error("❌ Sauvegarde dashboard échouée:", e);
      toastError("Sauvegarde impossible : " + msg);
      return false;
    }
  }

  async function loadDashboard() {
    if (!token) return;
    setLoading(true);
    try {
      const d = await getDataset(token, id);
      setDataset(d);

      if (!d.auto_kpis || d.auto_kpis.specs.length === 0) {
        await generateAutoKpis(token, id);
        await generateAdvancedKpis(token, id);
        const refreshed = await getDataset(token, id);
        setDataset(refreshed);
      }

      const refreshed = await getDataset(token, id);
      const results = await calculateAllKpis(token, id);
      setKpiResults(results);

      // Sauvegarde auto avec erreurs visibles
      await persistDashboard(refreshed, results);
    } catch (e) {
      toastError(e instanceof Error ? e.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (!token) {
      router.push("/login");
      return;
    }
    if (!id) return;
    loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, token, id]);

  useEffect(() => {
    if (dataset) {
      document.title = `📊 ${dataset.name} · Vector Dashboard`;
    }
  }, [dataset]);

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopiedLink(true);
      success("Lien copié dans le presse-papier !");
      setTimeout(() => setCopiedLink(false), 2000);
    } catch {
      toastError("Impossible de copier le lien");
    }
  }

  async function handleRegenerate() {
    if (!token) return;
    setRegenerating(true);
    try {
      await generateAutoKpis(token, id);
      await generateAdvancedKpis(token, id);
      const refreshed = await getDataset(token, id);
      setDataset(refreshed);
      const results = await calculateAllKpis(token, id);
      setKpiResults(results);

      const ok = await persistDashboard(refreshed, results);
      if (ok) {
        success(`Dashboard régénéré et sauvegardé : ${results.length} KPIs`);
      } else {
        success(`Dashboard régénéré : ${results.length} KPIs (non sauvegardé)`);
      }
    } catch (e) {
      toastError(e instanceof Error ? e.message : "Erreur de régénération");
    } finally {
      setRegenerating(false);
    }
  }

  if (!hydrated) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 size={40} className="animate-spin text-emerald-400 mx-auto mb-4" />
          <p className="text-muted-foreground text-base font-medium">Connexion en cours...</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <header className="sticky top-0 z-40 bg-background/90 backdrop-blur-md border-b border-border">
          <div className="max-w-7xl mx-auto px-8 py-4 flex items-center gap-4">
            <div className="w-9 h-9 rounded-lg bg-muted animate-pulse" />
            <div className="space-y-2">
              <div className="h-3 w-24 bg-muted rounded animate-pulse" />
              <div className="h-4 w-32 bg-muted rounded animate-pulse" />
            </div>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-8 py-10">
          <KpiDashboardSkeleton />
        </main>
      </div>
    );
  }

  if (!dataset) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-red-400 text-sm">Dataset introuvable</p>
      </div>
    );
  }

  const semantic = dataset.semantic_analysis;
  const domainLabel = semantic?.llm_analysis?.domain_label || "Dataset";
  const qualityPct = dataset.quality_score != null ? Math.round(dataset.quality_score * 100) : null;
  const safeFilename = dataset.name.replace(/[^a-zA-Z0-9_-]/g, "_");

  return (
    <div className="min-h-screen bg-background text-foreground">
      <ToastContainer toasts={toasts} onClose={removeToast} />

      {/* Topbar standalone */}
      <header className="sticky top-0 z-40 bg-background/90 backdrop-blur-md border-b border-border print:hidden">
        <div className="max-w-7xl mx-auto px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-base font-bold shadow-lg shadow-emerald-900/40">
              V
            </div>
            <div>
              <p className="text-xs uppercase tracking-wider text-emerald-400 font-semibold">
                Dashboard Vector
              </p>
              <h1 className="text-base font-bold text-foreground leading-tight">
                {dataset.name}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyLink}
              className="px-3 py-2 bg-card hover:bg-muted border border-border rounded-lg text-xs text-foreground flex items-center gap-2 transition-colors"
              title="Copier le lien du dashboard"
            >
              {copiedLink ? (
                <>
                  <Check size={13} className="text-emerald-400" />
                  Copié !
                </>
              ) : (
                <>
                  <Link2 size={13} />
                  Partager
                </>
              )}
            </button>
            <ExportButton filename={"vector-" + safeFilename} />
            <button
              onClick={handleRegenerate}
              disabled={regenerating}
              className="px-3 py-2 bg-card hover:bg-muted border border-border disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-xs text-foreground flex items-center gap-2 transition-colors"
              title="Régénérer le dashboard à partir des données actuelles"
            >
              <RefreshCw size={13} className={regenerating ? "animate-spin" : ""} />
              {regenerating ? "Régénération..." : "Régénérer"}
            </button>
            <button
              onClick={() => window.close()}
              className="px-3 py-2 bg-card hover:bg-muted border border-border rounded-lg text-xs text-muted-foreground hover:text-foreground flex items-center gap-2 transition-colors"
              title="Fermer l'onglet"
            >
              <LogOut size={13} />
              Fermer
            </button>
          </div>
        </div>
      </header>

      {/* Zone exportable */}
      <main id="dashboard-export" className="max-w-7xl mx-auto px-8 py-10">
        {/* Métadonnées dataset */}
        <div className="mb-10">
          <div className="flex items-center gap-2 mb-3">
            <Database size={14} className="text-muted-foreground" />
            <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">
              {dataset.original_filename}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
            <span className="text-foreground font-medium">{domainLabel}</span>
            <span className="text-muted-foreground">·</span>
            <span className="text-muted-foreground">{dataset.row_count?.toLocaleString("fr-FR")} lignes</span>
            <span className="text-muted-foreground">·</span>
            <span className="text-muted-foreground">{dataset.column_count} colonnes</span>
            {qualityPct != null && (
              <>
                <span className="text-muted-foreground">·</span>
                <span
                  className={
                    "px-2 py-0.5 rounded text-xs font-medium border " +
                    (qualityPct >= 90
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      : qualityPct >= 70
                      ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                      : "bg-red-500/10 text-red-400 border-red-500/30")
                  }
                >
                  Qualité {qualityPct}%
                </span>
              </>
            )}
          </div>
          {semantic?.llm_analysis?.description && (
            <p className="text-sm text-muted-foreground mt-3 max-w-3xl leading-relaxed">
              {semantic.llm_analysis.description}
            </p>
          )}
        </div>

        {dataset.auto_kpis && kpiResults.length > 0 ? (
          <KpiDashboard specs={dataset.auto_kpis.specs} results={kpiResults} />
        ) : (
          <div className="bg-card/30 rounded-xl p-12 text-center border border-dashed border-border">
            <p className="text-muted-foreground text-sm">
              Aucun KPI disponible.
            </p>
          </div>
        )}

        <footer className="mt-16 pt-8 border-t border-border text-center">
          <p className="text-xs text-muted-foreground">
            Généré par Vector · Commando IA d&apos;A.I. Commandos ·{" "}
            {new Date().toLocaleDateString("fr-FR", {
              day: "2-digit",
              month: "long",
              year: "numeric",
            })}
          </p>
        </footer>
      </main>
    </div>
  );
}