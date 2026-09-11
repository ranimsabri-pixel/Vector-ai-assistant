"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, X } from "lucide-react";

import { useAuthStore } from "@/lib/store/auth";
import { listDatasets, type Dataset } from "@/lib/datasets";
import { createSavedDashboard, type SavedDashboardDetail } from "@/lib/dashboards";

type DashboardCreateModalProps = {
  open: boolean;
  onClose: () => void;
  onCreated: (dashboard: SavedDashboardDetail) => void;
};

export function DashboardCreateModal({
  open,
  onClose,
  onCreated,
}: DashboardCreateModalProps) {
  const token = useAuthStore((s) => s.token);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loadingDatasets, setLoadingDatasets] = useState(false);
  const [saving, setSaving] = useState(false);

  // Réinitialise le formulaire à chaque ouverture
  useEffect(() => {
    if (!open) return;
    setName("");
    setDescription("");
    setDatasetId("");

    if (!token) return;
    setLoadingDatasets(true);
    listDatasets(token)
      .then((all) => setDatasets(all.filter((d) => d.status === "ready")))
      .catch((e) => {
        toast.error(e instanceof Error ? e.message : "Erreur de chargement des datasets");
      })
      .finally(() => setLoadingDatasets(false));
  }, [open, token]);

  async function handleCreate() {
    if (!token) return;
    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("Le nom du dashboard est obligatoire");
      return;
    }
    if (!datasetId) {
      toast.error("Choisis un dataset");
      return;
    }

    setSaving(true);
    try {
      const dashboard = await createSavedDashboard(token, {
        name: trimmedName,
        description: description.trim() || null,
        dataset_id: datasetId,
      });
      toast.success(`Dashboard "${dashboard.name}" créé`);
      onCreated(dashboard);
      onClose();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de création");
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/60 z-40 animate-fade-in"
        onClick={onClose}
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="w-full max-w-lg bg-card border border-border rounded-2xl shadow-2xl animate-message-in pointer-events-auto overflow-hidden flex flex-col max-h-[85vh]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-5 border-b border-border shrink-0">
            <h2 className="text-base font-semibold text-foreground">
              Créer un tableau de bord
            </h2>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Fermer"
            >
              <X size={16} />
            </button>
          </div>

          <div className="p-5 space-y-4 overflow-y-auto">
            <div>
              <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                Nom
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ex: Suivi ventes T1"
                autoFocus
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                Description (optionnel)
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="À quoi sert ce dashboard ?"
                rows={2}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60 resize-none transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                Dataset source
              </label>
              {loadingDatasets ? (
                <div className="flex items-center justify-center gap-2 py-4 text-xs text-muted-foreground border border-border rounded-lg">
                  <Loader2 size={14} className="animate-spin" />
                  Chargement des datasets...
                </div>
              ) : datasets.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4 italic border border-border rounded-lg">
                  Aucun dataset prêt disponible. Importe et profile un dataset
                  depuis la page Mes données.
                </p>
              ) : (
                <select
                  value={datasetId}
                  onChange={(e) => setDatasetId(e.target.value)}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
                >
                  <option value="">Sélectionner un dataset...</option>
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          <div className="flex gap-2 p-4 bg-background/50 border-t border-border shrink-0">
            <button
              onClick={onClose}
              disabled={saving}
              className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors disabled:opacity-40"
            >
              Annuler
            </button>
            <button
              onClick={handleCreate}
              disabled={saving || !name.trim() || !datasetId}
              className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {saving && <Loader2 size={14} className="animate-spin" />}
              Créer et éditer
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
