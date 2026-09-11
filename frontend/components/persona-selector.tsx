"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ChevronDown, Lock } from "lucide-react";

import { useAuthStore } from "@/lib/store/auth";
import { useDiscussionsStore } from "@/lib/store/discussions";
import { listPersonas, type PersonaListItem } from "@/lib/personas";
import { PersonaIcon } from "./persona-icon";

const DEFAULT_NAME = "Vector";
const DEFAULT_ICON = "Bot";
const DEFAULT_COLOR = "#2D8659";

type PersonaSelectorProps = {
  /** Nombre de messages de la conversation active — verrouille des que > 0. */
  messageCount: number;
};

export function PersonaSelector({ messageCount }: PersonaSelectorProps) {
  const token = useAuthStore((s) => s.token);
  const activeId = useDiscussionsStore((s) => s.activeId);
  const discussion = useDiscussionsStore((s) =>
    s.discussions.find((d) => d.id === s.activeId),
  );
  const setPersona = useDiscussionsStore((s) => s.setPersona);

  const [open, setOpen] = useState(false);
  const [personas, setPersonas] = useState<PersonaListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const locked = messageCount > 0;
  // Pas d'id backend encore (creation optimiste en cours) -> pas d'action possible.
  const isPending = !activeId || discussion?.pending;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  async function handleOpen() {
    if (locked || isPending) return;
    setOpen((o) => !o);
    if (!open && token && personas.length === 0) {
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
  }

  async function handlePick(persona: PersonaListItem) {
    if (!token || !activeId) return;
    setOpen(false);
    try {
      await setPersona(token, activeId, {
        id: persona.id,
        name: persona.name,
        icon: persona.icon,
        color: persona.color,
      });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de changement de persona");
    }
  }

  if (!activeId) return null;

  const name = discussion?.personaName ?? DEFAULT_NAME;
  const icon = discussion?.personaIcon ?? DEFAULT_ICON;
  const color = discussion?.personaColor ?? DEFAULT_COLOR;

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        data-testid="persona-selector-badge"
        data-locked={locked}
        onClick={handleOpen}
        disabled={locked || isPending}
        title={locked ? "Persona verrouillé (conversation déjà commencée)" : "Changer de persona"}
        className={`flex items-center gap-1.5 pl-1.5 pr-2 py-1 rounded-full text-xs font-medium border transition-colors ${
          locked || isPending
            ? "border-border text-muted-foreground cursor-default"
            : "border-border text-foreground hover:border-border hover:bg-card cursor-pointer"
        }`}
      >
        <span
          className="w-4 h-4 rounded-full flex items-center justify-center shrink-0"
          style={{ backgroundColor: color }}
        >
          <PersonaIcon name={icon} size={10} className="text-white" />
        </span>
        {name}
        {locked ? <Lock size={10} /> : <ChevronDown size={10} />}
      </button>

      {open && !locked && !isPending && (
        <div className="absolute bottom-full mb-2 left-0 w-56 bg-card border border-border rounded-lg shadow-xl overflow-hidden z-20 animate-fade-in">
          {loading ? (
            <div className="px-3 py-3 text-xs text-muted-foreground">Chargement...</div>
          ) : personas.length === 0 ? (
            <div className="px-3 py-3 text-xs text-muted-foreground">Aucun persona disponible.</div>
          ) : (
            <div className="max-h-64 overflow-y-auto py-1">
              {personas.map((persona) => (
                <button
                  key={persona.id}
                  type="button"
                  data-testid="persona-option"
                  onClick={() => handlePick(persona)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors text-left"
                >
                  <span
                    className="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                    style={{ backgroundColor: persona.color }}
                  >
                    <PersonaIcon name={persona.icon} size={11} className="text-white" />
                  </span>
                  <span className="truncate">{persona.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
