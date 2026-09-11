"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, FileText, Layers, Loader2, X } from "lucide-react";

import { useAuthStore } from "@/lib/store/auth";
import { fetchUserDocuments, type DocumentSummary } from "@/lib/documents";
import { listCorpora, type CorpusSummary } from "@/lib/corpus";
import {
  PERSONA_ICONS,
  PERSONA_COLORS,
  createPersona,
  updatePersona,
  linkDocumentsToPersona,
  unlinkDocumentFromPersona,
  linkCorporaToPersona,
  unlinkCorpusFromPersona,
  type PersonaDetail,
} from "@/lib/personas";
import { PersonaIcon } from "./persona-icon";

type PersonaFormModalProps = {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  /** Persona à éditer, ou null pour une création. */
  persona: PersonaDetail | null;
};

const DEFAULT_ICON = "Bot";
const DEFAULT_COLOR = PERSONA_COLORS[0];

export function PersonaFormModal({
  open,
  onClose,
  onSaved,
  persona,
}: PersonaFormModalProps) {
  const token = useAuthStore((s) => s.token);
  const editing = persona !== null;

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [icon, setIcon] = useState<string>(DEFAULT_ICON);
  const [color, setColor] = useState<string>(DEFAULT_COLOR);

  const [allDocuments, setAllDocuments] = useState<DocumentSummary[]>([]);
  const [allCorpora, setAllCorpora] = useState<CorpusSummary[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [selectedCorpusIds, setSelectedCorpusIds] = useState<Set<string>>(new Set());

  const [loadingSources, setLoadingSources] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !token) return;

    setName(persona?.name ?? "");
    setDescription(persona?.description ?? "");
    setSystemPrompt(persona?.system_prompt ?? "");
    setIcon(persona?.icon ?? DEFAULT_ICON);
    setColor(persona?.color ?? DEFAULT_COLOR);
    setSelectedDocIds(new Set(persona?.documents.map((d) => d.id) ?? []));
    setSelectedCorpusIds(new Set(persona?.corpora.map((c) => c.id) ?? []));

    setLoadingSources(true);
    Promise.all([fetchUserDocuments(token), listCorpora(token)])
      .then(([docs, corpora]) => {
        setAllDocuments(docs);
        setAllCorpora(corpora);
      })
      .catch((e) => toast.error(e instanceof Error ? e.message : "Erreur de chargement"))
      .finally(() => setLoadingSources(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, token, persona?.id]);

  function toggleDoc(id: string) {
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleCorpus(id: string) {
    setSelectedCorpusIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function reconcileSources(personaId: string) {
    const originalDocIds = new Set(persona?.documents.map((d) => d.id) ?? []);
    const originalCorpusIds = new Set(persona?.corpora.map((c) => c.id) ?? []);

    const docsToAdd = [...selectedDocIds].filter((id) => !originalDocIds.has(id));
    const docsToRemove = [...originalDocIds].filter((id) => !selectedDocIds.has(id));
    const corporaToAdd = [...selectedCorpusIds].filter((id) => !originalCorpusIds.has(id));
    const corporaToRemove = [...originalCorpusIds].filter((id) => !selectedCorpusIds.has(id));

    if (!token) return;
    if (docsToAdd.length) await linkDocumentsToPersona(token, personaId, docsToAdd);
    for (const id of docsToRemove) await unlinkDocumentFromPersona(token, personaId, id);
    if (corporaToAdd.length) await linkCorporaToPersona(token, personaId, corporaToAdd);
    for (const id of corporaToRemove) await unlinkCorpusFromPersona(token, personaId, id);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;

    setSaving(true);
    try {
      if (editing && persona) {
        await updatePersona(token, persona.id, {
          name,
          description: description || null,
          system_prompt: systemPrompt,
          icon,
          color,
        });
        await reconcileSources(persona.id);
        toast.success(`Persona "${name}" mis à jour`);
      } else {
        const created = await createPersona(token, {
          name,
          description: description || null,
          system_prompt: systemPrompt,
          icon,
          color,
        });
        await reconcileSources(created.id);
        toast.success(`Persona "${name}" créé`);
      }
      onSaved();
      onClose();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur d'enregistrement");
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  const nameValid = name.trim().length >= 1 && name.trim().length <= 60;
  const promptValid = systemPrompt.trim().length >= 10 && systemPrompt.trim().length <= 5000;
  const canSubmit = nameValid && promptValid && !saving;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/60 z-40 animate-fade-in"
        onClick={onClose}
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="w-full max-w-2xl max-h-[90vh] bg-card border border-border rounded-2xl shadow-2xl animate-message-in pointer-events-auto overflow-hidden flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-5 border-b border-border shrink-0">
            <h2 className="text-base font-semibold text-foreground">
              {editing ? "Modifier le persona" : "Créer un persona"}
            </h2>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Fermer"
            >
              <X size={16} />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="overflow-y-auto flex-1">
            <div className="p-5 space-y-5">
              {/* Nom */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  Nom
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={60}
                  placeholder="ex: Vector Finance"
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  Description (optionnelle)
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  maxLength={500}
                  placeholder="À quoi sert ce persona ?"
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60"
                />
              </div>

              {/* System prompt */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  Prompt système
                </label>
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={6}
                  maxLength={5000}
                  placeholder="Tu es un analyste financier. Réponds toujours avec des ratios quand pertinent."
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/60 resize-none font-mono"
                />
                <p className="text-[11px] text-muted-foreground mt-1">
                  {systemPrompt.trim().length}/5000 caractères (10 minimum)
                </p>
              </div>

              {/* Icône */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  Icône
                </label>
                <div className="grid grid-cols-10 gap-2">
                  {PERSONA_ICONS.map((iconName) => (
                    <button
                      key={iconName}
                      type="button"
                      onClick={() => setIcon(iconName)}
                      title={iconName}
                      className={`aspect-square flex items-center justify-center rounded-lg border transition-colors ${
                        icon === iconName
                          ? "border-emerald-500 bg-emerald-600/10 text-emerald-400"
                          : "border-border bg-background text-muted-foreground hover:border-border hover:text-foreground"
                      }`}
                    >
                      <PersonaIcon name={iconName} size={16} />
                    </button>
                  ))}
                </div>
              </div>

              {/* Couleur */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  Couleur d&apos;accent
                </label>
                <div className="flex gap-2">
                  {PERSONA_COLORS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setColor(c)}
                      title={c}
                      style={{ backgroundColor: c }}
                      className={`w-8 h-8 rounded-full flex items-center justify-center transition-transform ${
                        color === c ? "ring-2 ring-offset-2 ring-offset-card ring-white scale-105" : ""
                      }`}
                    >
                      {color === c && <Check size={14} className="text-white" />}
                    </button>
                  ))}
                </div>
              </div>

              {/* Documents associés */}
              <div>
                <label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  <FileText size={12} />
                  Documents associés
                </label>
                {loadingSources ? (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
                    <Loader2 size={12} className="animate-spin" /> Chargement...
                  </div>
                ) : allDocuments.length === 0 ? (
                  <p className="text-xs text-muted-foreground">Aucun document disponible.</p>
                ) : (
                  <div className="max-h-32 overflow-y-auto border border-border rounded-lg divide-y divide-border">
                    {allDocuments.map((doc) => (
                      <label
                        key={doc.id}
                        className="flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted/50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedDocIds.has(doc.id)}
                          onChange={() => toggleDoc(doc.id)}
                          className="w-3.5 h-3.5 rounded border-border bg-background text-emerald-600 focus:ring-emerald-500/50 focus:ring-offset-0"
                        />
                        <span className="truncate">{doc.name}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              {/* Corpus associés */}
              <div>
                <label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  <Layers size={12} />
                  Corpus associés
                </label>
                {loadingSources ? (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
                    <Loader2 size={12} className="animate-spin" /> Chargement...
                  </div>
                ) : allCorpora.length === 0 ? (
                  <p className="text-xs text-muted-foreground">Aucun corpus disponible.</p>
                ) : (
                  <div className="max-h-32 overflow-y-auto border border-border rounded-lg divide-y divide-border">
                    {allCorpora.map((corpus) => (
                      <label
                        key={corpus.id}
                        className="flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted/50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedCorpusIds.has(corpus.id)}
                          onChange={() => toggleCorpus(corpus.id)}
                          className="w-3.5 h-3.5 rounded border-border bg-background text-emerald-600 focus:ring-emerald-500/50 focus:ring-offset-0"
                        />
                        <span className="truncate">{corpus.name}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="flex gap-2 p-4 bg-background/50 border-t border-border shrink-0">
              <button
                type="button"
                onClick={onClose}
                disabled={saving}
                className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors disabled:opacity-40"
              >
                Annuler
              </button>
              <button
                type="submit"
                disabled={!canSubmit}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 transition-colors disabled:opacity-40"
              >
                {saving && <Loader2 size={14} className="animate-spin" />}
                {editing ? "Enregistrer" : "Créer le persona"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}
