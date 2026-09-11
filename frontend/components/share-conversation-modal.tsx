"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Copy, Loader2, X } from "lucide-react";

import { useAuthStore } from "@/lib/store/auth";
import { createShare, revokeShare } from "@/lib/shares";

type ShareConversationModalProps = {
  open: boolean;
  onClose: () => void;
  conversationId: string;
};

export function ShareConversationModal({
  open,
  onClose,
  conversationId,
}: ShareConversationModalProps) {
  const token = useAuthStore((s) => s.token);

  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [revoking, setRevoking] = useState(false);
  // Securite par defaut : decochee a l'ouverture, a chaque fois (pas de
  // memoire de la derniere preference entre deux ouvertures de la modal).
  const [includeAttachments, setIncludeAttachments] = useState(false);
  const [updatingPreference, setUpdatingPreference] = useState(false);

  // A l'ouverture : cree le lien (ou recupere l'actif existant — POST est
  // idempotent cote backend, pas de doublon).
  useEffect(() => {
    if (!open || !token) return;
    setShareUrl(null);
    setCopied(false);
    setIncludeAttachments(false);
    setLoading(true);
    createShare(token, conversationId, false)
      .then((res) => setShareUrl(res.share_url))
      .catch((e) => {
        toast.error(e instanceof Error ? e.message : "Erreur de création du lien");
        onClose();
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, token, conversationId]);

  async function handleToggleAttachments(checked: boolean) {
    if (!token) return;
    setIncludeAttachments(checked);
    setUpdatingPreference(true);
    try {
      const res = await createShare(token, conversationId, checked);
      setShareUrl(res.share_url);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de mise à jour");
      setIncludeAttachments(!checked);
    } finally {
      setUpdatingPreference(false);
    }
  }

  async function handleCopy() {
    if (!shareUrl) return;
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    toast.success("Lien copié");
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleRevoke() {
    if (!token) return;
    setRevoking(true);
    try {
      await revokeShare(token, conversationId);
      toast.success("Partage révoqué — le lien n'est plus valide");
      onClose();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur lors de la révocation");
    } finally {
      setRevoking(false);
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
          className="w-full max-w-lg bg-card border border-border rounded-2xl shadow-2xl animate-message-in pointer-events-auto overflow-hidden flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between p-5 border-b border-border shrink-0">
            <h2 className="text-base font-semibold text-foreground">
              Partager cette conversation
            </h2>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Fermer"
            >
              <X size={16} />
            </button>
          </div>

          <div className="p-5 space-y-4">
            <p className="text-sm text-muted-foreground">
              Toute personne avec ce lien pourra voir la conversation en
              lecture seule, sans avoir besoin de compte.
            </p>

            {loading ? (
              <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
                <Loader2 size={16} className="animate-spin" />
                Génération du lien...
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={shareUrl ?? ""}
                  onClick={(e) => e.currentTarget.select()}
                  className="flex-1 px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
                />
                <button
                  onClick={handleCopy}
                  disabled={!shareUrl}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 transition-colors disabled:opacity-40 shrink-0"
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                  {copied ? "Copié" : "Copier le lien"}
                </button>
              </div>
            )}

            <label className="flex items-start gap-2.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={includeAttachments}
                disabled={loading || updatingPreference}
                onChange={(e) => handleToggleAttachments(e.target.checked)}
                className="mt-0.5 w-4 h-4 rounded border-border bg-background text-emerald-600 focus:ring-emerald-500/50 focus:ring-offset-0 disabled:opacity-40"
              />
              <span className="text-sm text-foreground">
                Inclure les images attachées dans la conversation partagée
                <span className="block text-xs text-muted-foreground mt-0.5">
                  Les images peuvent contenir des données sensibles. Ne les
                  incluez que si vous êtes sûr(e).
                </span>
              </span>
            </label>
          </div>

          <div className="flex gap-2 p-4 bg-background/50 border-t border-border shrink-0">
            <button
              onClick={onClose}
              disabled={revoking}
              className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors disabled:opacity-40"
            >
              Fermer
            </button>
            <button
              onClick={handleRevoke}
              disabled={loading || revoking || !shareUrl}
              className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-red-400 hover:bg-red-500/10 border border-red-500/30 transition-colors disabled:opacity-40 flex items-center justify-center gap-2"
            >
              {revoking && <Loader2 size={14} className="animate-spin" />}
              Révoquer le partage
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
