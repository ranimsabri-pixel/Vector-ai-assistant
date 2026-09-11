"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Sparkles } from "lucide-react";

import { useAuthStore } from "@/lib/store/auth";
import { useConfirm } from "@/lib/hooks/use-confirm";
import { ConfirmDialog } from "@/components/confirm_dialog";
import { EmptyState } from "@/components/empty_state";
import { PersonaCard } from "@/components/persona-card";
import { PersonaFormModal } from "@/components/persona-form-modal";
import {
  listPersonas,
  fetchPersona,
  deletePersona,
  type PersonaListItem,
  type PersonaDetail,
} from "@/lib/personas";

export default function PersonasPage() {
  const token = useAuthStore((s) => s.token);
  const { confirm, dialogProps } = useConfirm();

  const [personas, setPersonas] = useState<PersonaListItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [modalOpen, setModalOpen] = useState(false);
  const [editingPersona, setEditingPersona] = useState<PersonaDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<string | null>(null);

  useEffect(() => {
    if (token) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function refresh() {
    if (!token) return;
    setLoading(true);
    try {
      const data = await listPersonas(token);
      setPersonas(data);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }

  function handleCreate() {
    setEditingPersona(null);
    setModalOpen(true);
  }

  async function handleEdit(personaId: string) {
    if (!token) return;
    setLoadingDetail(personaId);
    try {
      const detail = await fetchPersona(token, personaId);
      setEditingPersona(detail);
      setModalOpen(true);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de chargement");
    } finally {
      setLoadingDetail(null);
    }
  }

  async function handleDelete(persona: PersonaListItem) {
    if (!token) return;

    const ok = await confirm({
      title: `Supprimer "${persona.name}" ?`,
      description:
        "Ce persona sera supprimé définitivement. Les conversations qui l'utilisaient garderont leur historique.",
      confirmLabel: "Supprimer",
      variant: "danger",
    });
    if (!ok) return;

    try {
      await deletePersona(token, persona.id);
      toast.success(`Persona "${persona.name}" supprimé`);
      await refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de suppression");
    }
  }

  return (
    <div className="h-full overflow-y-auto bg-background">
      <div className="max-w-4xl mx-auto px-8 py-10">
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-4xl font-bold mb-2 tracking-tight">
              <span className="text-foreground">Mes </span>
              <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
                personas
              </span>
            </h1>
            <p className="text-sm text-muted-foreground">
              Des assistants sur-mesure : prompt système, documents et corpus dédiés.
            </p>
          </div>
          <button
            onClick={handleCreate}
            className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm font-medium text-white transition-colors shrink-0"
          >
            <Plus size={16} />
            Créer un persona
          </button>
        </div>

        {loading && personas.length === 0 ? (
          <div className="text-sm text-muted-foreground">Chargement...</div>
        ) : personas.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="Aucun persona pour l'instant"
            description="Crée ton premier assistant sur-mesure avec le bouton ci-dessus."
          />
        ) : (
          <div className="space-y-2 pb-8">
            {personas.map((persona) => (
              <PersonaCard
                key={persona.id}
                persona={persona}
                onEdit={() => handleEdit(persona.id)}
                onDelete={() => handleDelete(persona)}
                editLoading={loadingDetail === persona.id}
              />
            ))}
          </div>
        )}
      </div>

      <PersonaFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={refresh}
        persona={editingPersona}
      />
      <ConfirmDialog {...dialogProps} />
    </div>
  );
}
