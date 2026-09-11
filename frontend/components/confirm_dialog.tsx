"use client";

import { AlertTriangle, Trash2 } from "lucide-react";
import { useEffect } from "react";

type ConfirmDialogProps = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning";
};

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirmer",
  cancelLabel = "Annuler",
  variant = "danger",
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      if (e.key === "Enter") onConfirm();
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose, onConfirm]);

  if (!open) return null;

  const isDanger = variant === "danger";
  const Icon = isDanger ? Trash2 : AlertTriangle;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/60 z-40 animate-fade-in"
        onClick={onClose}
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          className="w-full max-w-md bg-card border border-border rounded-2xl shadow-2xl animate-message-in pointer-events-auto overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-6">
            <div
              className={`w-11 h-11 rounded-xl flex items-center justify-center mb-4 ${
                isDanger
                  ? "bg-red-950/50 border border-red-900/60"
                  : "bg-amber-950/50 border border-amber-900/60"
              }`}
            >
              <Icon
                size={20}
                className={isDanger ? "text-red-400" : "text-amber-400"}
              />
            </div>
            <h2 className="text-base font-semibold text-foreground mb-1.5">
              {title}
            </h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {description}
            </p>
          </div>

          <div className="flex gap-2 p-4 bg-background/50 border-t border-border">
            <button
              data-testid="confirm-dialog-cancel"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
            >
              {cancelLabel}
            </button>
            <button
              data-testid="confirm-dialog-confirm"
              onClick={() => {
                onConfirm();
                onClose();
              }}
              className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-white transition-colors ${
                isDanger
                  ? "bg-red-600 hover:bg-red-500"
                  : "bg-amber-600 hover:bg-amber-500"
              }`}
              autoFocus
            >
              {confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}