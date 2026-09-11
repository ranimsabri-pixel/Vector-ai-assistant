"use client";

import { useState } from "react";
import { Check, Copy, RefreshCw, ThumbsDown, ThumbsUp } from "lucide-react";
import { toast } from "sonner";
import type { MessageFeedback } from "@/lib/messages";

interface MessageActionsProps {
  messageId: string;
  messageText: string;
  currentFeedback: MessageFeedback;
  onRegenerate: () => void;
  onFeedbackChange: (feedback: MessageFeedback) => void;
  disabled?: boolean;
}

const BASE_BTN =
  "p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted " +
  "transition-colors disabled:opacity-40 disabled:cursor-not-allowed " +
  "active:scale-90 transition-transform duration-100";

// Fallback pour les navigateurs sans navigator.clipboard (ou hors contexte
// sécurisé, ex. accès en http:// sur le réseau local) : execCommand est
// deprecated mais reste le seul filet de sécurité fonctionnel dans ce cas.
function copyViaExecCommand(text: string): boolean {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  let success = false;
  try {
    success = document.execCommand("copy");
  } catch {
    success = false;
  }
  document.body.removeChild(textarea);
  return success;
}

async function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // tombe en fallback ci-dessous
    }
  }
  return copyViaExecCommand(text);
}

export function MessageActions({
  messageText,
  currentFeedback,
  onRegenerate,
  onFeedbackChange,
  disabled = false,
}: MessageActionsProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    const ok = await copyToClipboard(messageText);
    if (ok) {
      setCopied(true);
      toast.success("Réponse copiée dans le presse-papier");
      setTimeout(() => setCopied(false), 2000);
    } else {
      toast.error("Impossible de copier, vérifie les permissions du navigateur");
    }
  }

  function handleThumbsUp() {
    onFeedbackChange(currentFeedback === "positive" ? null : "positive");
  }

  function handleThumbsDown() {
    onFeedbackChange(currentFeedback === "negative" ? null : "negative");
  }

  return (
    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
      <button
        type="button"
        onClick={onRegenerate}
        disabled={disabled}
        className={BASE_BTN}
        title="Régénérer"
      >
        <RefreshCw size={14} />
      </button>

      <button
        type="button"
        onClick={handleCopy}
        disabled={disabled}
        className={BASE_BTN}
        title="Copier"
      >
        {copied ? (
          <Check size={14} className="text-emerald-400 animate-fade-in" />
        ) : (
          <Copy size={14} />
        )}
      </button>

      <button
        type="button"
        onClick={handleThumbsUp}
        disabled={disabled}
        className={
          BASE_BTN +
          (currentFeedback === "positive"
            ? " text-emerald-400 bg-emerald-500/10 hover:text-emerald-300"
            : "")
        }
        title="Utile"
      >
        <ThumbsUp size={14} />
      </button>

      <button
        type="button"
        onClick={handleThumbsDown}
        disabled={disabled}
        className={
          BASE_BTN +
          (currentFeedback === "negative"
            ? " text-red-400 bg-red-500/10 hover:text-red-300"
            : "")
        }
        title="À améliorer"
      >
        <ThumbsDown size={14} />
      </button>
    </div>
  );
}
