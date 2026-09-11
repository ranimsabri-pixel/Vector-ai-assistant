"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";

type DeleteAccountModalProps = {
  open: boolean;
  onClose: () => void;
  onConfirm: (password: string) => Promise<void>;
};

const CONFIRM_WORD = "SUPPRIMER";

export function DeleteAccountModal({ open, onClose, onConfirm }: DeleteAccountModalProps) {
  const [password, setPassword] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) {
      setPassword("");
      setConfirmText("");
      setError(null);
      setLoading(false);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  const canConfirm = password.length > 0 && confirmText === CONFIRM_WORD && !loading;

  async function handleConfirm() {
    if (!canConfirm) return;
    setError(null);
    setLoading(true);
    try {
      await onConfirm(password);
    } catch {
      setError("Mot de passe incorrect");
      setLoading(false);
    }
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/60 z-40 animate-fade-in" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="w-full max-w-md bg-card border border-border rounded-2xl shadow-2xl animate-message-in pointer-events-auto overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-6">
            <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-4 bg-red-950/50 border border-red-900/60">
              <AlertTriangle size={20} className="text-red-400" />
            </div>
            <h2 className="text-base font-semibold text-foreground mb-1.5">
              Supprimer définitivement mon compte
            </h2>
            <p className="text-sm text-muted-foreground leading-relaxed mb-4">
              Cette action est <strong className="text-foreground">irréversible</strong>. Tous
              tes datasets, documents, conversations et personas seront supprimés
              définitivement, sans possibilité de récupération.
            </p>

            <div className="space-y-3">
              <div>
                <label htmlFor="delete-password" className="block text-xs mb-1 text-muted-foreground">
                  Mot de passe
                </label>
                <input
                  id="delete-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-red-500 transition-colors"
                />
              </div>
              <div>
                <label htmlFor="delete-confirm" className="block text-xs mb-1 text-muted-foreground">
                  Tape <strong className="text-foreground">{CONFIRM_WORD}</strong> pour confirmer
                </label>
                <input
                  id="delete-confirm"
                  type="text"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  autoComplete="off"
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-red-500 transition-colors"
                />
              </div>
            </div>

            {error && <p className="text-sm text-red-400 mt-3">{error}</p>}
          </div>

          <div className="flex gap-2 p-4 bg-background/50 border-t border-border">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
            >
              Annuler
            </button>
            <button
              data-testid="delete-account-confirm"
              onClick={handleConfirm}
              disabled={!canConfirm}
              className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Suppression..." : "Supprimer définitivement"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
