"use client";

import { Lock, Pencil, Trash2 } from "lucide-react";
import { PersonaIcon } from "./persona-icon";
import type { PersonaListItem } from "@/lib/personas";

type PersonaCardProps = {
  persona: PersonaListItem;
  onEdit: () => void;
  onDelete: () => void;
  editLoading?: boolean;
};

export function PersonaCard({ persona, onEdit, onDelete, editLoading }: PersonaCardProps) {
  return (
    <div
      data-testid="persona-card"
      data-persona-name={persona.name}
      className="flex items-start gap-4 p-4 bg-card/50 border border-border rounded-xl hover:border-border transition-colors"
      style={{ borderLeftColor: persona.color, borderLeftWidth: 3 }}
    >
      <div
        className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
        style={{ backgroundColor: persona.color }}
      >
        <PersonaIcon name={persona.icon} size={18} className="text-white" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 mb-0.5">
          <p className="text-sm font-medium text-foreground truncate">
            {persona.name}
          </p>
          {persona.is_system && (
            <span
              title="Persona système — non modifiable"
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground shrink-0"
            >
              <Lock size={9} />
              Système
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground line-clamp-2">
          {persona.description || "Aucune description"}
        </p>
      </div>

      {!persona.is_system && (
        <div className="flex items-center gap-1 shrink-0">
          <button
            data-testid="persona-edit-button"
            onClick={onEdit}
            disabled={editLoading}
            className="p-2 hover:bg-emerald-600/10 rounded-lg text-muted-foreground hover:text-emerald-400 transition-colors disabled:opacity-40"
            title="Modifier"
          >
            <Pencil size={15} />
          </button>
          <button
            data-testid="persona-delete-button"
            onClick={onDelete}
            className="p-2 hover:bg-red-600/10 rounded-lg text-muted-foreground hover:text-red-400 transition-colors"
            title="Supprimer"
          >
            <Trash2 size={15} />
          </button>
        </div>
      )}
    </div>
  );
}
