"use client";

import { X } from "lucide-react";
import { useEffect } from "react";

type HelpPanelProps = {
  open: boolean;
  onClose: () => void;
};

// Kbd component : affiche une touche stylée
function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex items-center justify-center px-2 py-1 rounded bg-muted border border-border text-xs font-mono text-foreground min-w-[24px]">
      {children}
    </kbd>
  );
}

export function HelpPanel({ open, onClose }: HelpPanelProps) {
  // Ferme sur Escape
  useEffect(() => {
    if (!open) return;
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 z-40 animate-fade-in"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="w-full max-w-lg bg-card border border-border rounded-2xl shadow-2xl animate-message-in pointer-events-auto"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-5 border-b border-border">
            <div>
              <h2 className="text-base font-semibold text-foreground">
                Raccourcis clavier
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Naviguez plus vite dans Vector
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Fermer"
            >
              <X size={18} />
            </button>
          </div>

          {/* Body */}
          <div className="p-5 space-y-5">
            <section>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-3">
                Discussions
              </p>
              <div className="space-y-2.5">
                <ShortcutRow
                  label="Nouvelle discussion"
                  keys={["Ctrl", "Shift", "O"]}
                />
                <ShortcutRow
                  label="Rechercher dans l'historique"
                  keys={["Ctrl", "K"]}
                />
              </div>
            </section>

            <section>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-3">
                Navigation
              </p>
              <div className="space-y-2.5">
                <ShortcutRow label="Afficher cette aide" keys={["?"]} />
                <ShortcutRow label="Fermer les panneaux" keys={["Esc"]} />
              </div>
            </section>
          </div>

          {/* Footer */}
          <div className="px-5 py-3 border-t border-border bg-background/50 rounded-b-2xl">
            <p className="text-[11px] text-muted-foreground text-center">
              Appuyez sur <Kbd>?</Kbd> à tout moment pour rouvrir cette aide
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

function ShortcutRow({ label, keys }: { label: string; keys: string[] }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-foreground">{label}</span>
      <div className="flex items-center gap-1">
        {keys.map((k, i) => (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <span className="text-muted-foreground text-xs">+</span>}
            <Kbd>{k}</Kbd>
          </span>
        ))}
      </div>
    </div>
  );
}