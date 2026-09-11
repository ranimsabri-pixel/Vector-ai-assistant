// components/agent_chat.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { SourceCard } from "@/components/source_card";
import { WebSourceCard } from "@/components/web_source_card";
import {
  Bot,
  User,
  Wrench,
  Loader2,
  AlertCircle,
  X,
  CheckCircle2,
  ExternalLink,
  FileSpreadsheet,
} from "lucide-react";

import type { AgentMessage } from "@/lib/hooks/use-agent-chat";
import type { ToolCallTrace } from "@/lib/agent";
import { QUICK_ACTIONS, type QuickAction } from "@/lib/quick_actions";
import { AgentForm, type FormSubmitPayload } from "@/components/agent_form";
import { MarkdownRenderer } from "@/components/markdown_renderer";
import { MessageActions } from "@/components/message_actions";
import type { MessageFeedback } from "@/lib/messages";
import { getFileTypeColorClass, getFileTypeLabel } from "@/lib/documents";

interface AgentChatProps {
  messages: AgentMessage[];
  loading: boolean;
  error: string | null;
  onActionClick: (action: QuickAction) => void;
  onFormSubmit: (
    messageId: string,
    action: QuickAction,
    payload: FormSubmitPayload,
  ) => void;
  onFormCancel: (messageId: string) => void;
  onClearError: () => void;
  onRegenerate: (messageId: string) => void;
  onFeedbackChange: (messageId: string, feedback: MessageFeedback) => void;
}

export default function AgentChat({
  messages,
  loading,
  error,
  onActionClick,
  onFormSubmit,
  onFormCancel,
  onClearError,
  onRegenerate,
  onFeedbackChange,
}: AgentChatProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const hasMessages = messages.length > 0;

  return (
    <div className="space-y-6">
      {/* ===== Erreur ===== */}
      {error && (
        <div className="flex items-start gap-3 bg-red-950/40 border border-red-900/50 rounded-xl px-4 py-3">
          <AlertCircle size={18} className="text-red-400 mt-0.5 flex-shrink-0" />
          <p className="flex-1 text-sm text-red-300">{error}</p>
          <button
            onClick={onClearError}
            className="text-red-400 hover:text-red-300 transition-colors"
            title="Fermer"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* ===== Actions rapides (affichées tant qu'il n'y a pas de conversation) ===== */}
      {!hasMessages && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {QUICK_ACTIONS.map((action) => {
            const Icon = action.Icon;
            return (
              <button
                key={action.id}
                onClick={() => onActionClick(action)}
                disabled={loading}
                className="text-left flex items-start gap-3 bg-card border border-border hover:border-emerald-600/50 hover:bg-card/80 rounded-xl px-4 py-3 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <div className="mt-0.5 p-1.5 bg-emerald-600/10 rounded-lg flex-shrink-0">
                  <Icon size={16} className="text-emerald-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {action.title}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {action.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* ===== Fil de conversation ===== */}
      <div className="space-y-4 animate-message-in">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            msg={msg}
            loading={loading}
            onFormSubmit={onFormSubmit}
            onFormCancel={onFormCancel}
            onRegenerate={onRegenerate}
            onFeedbackChange={onFeedbackChange}
          />
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground pl-1">
            <Loader2 size={14} className="animate-spin" />
            Vector travaille…
          </div>
        )}
      </div>

      <div ref={bottomRef} />
    </div>
  );
}

function MessageBubble({
  msg,
  loading,
  onFormSubmit,
  onFormCancel,
  onRegenerate,
  onFeedbackChange,
}: {
  msg: AgentMessage;
  loading: boolean;
  onFormSubmit: AgentChatProps["onFormSubmit"];
  onFormCancel: AgentChatProps["onFormCancel"];
  onRegenerate: AgentChatProps["onRegenerate"];
  onFeedbackChange: AgentChatProps["onFeedbackChange"];
}) {
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!lightboxSrc) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setLightboxSrc(null);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [lightboxSrc]);

  switch (msg.kind) {
    case "user":
      return (
        <div className="flex justify-end">
          <div className="flex items-start gap-2 max-w-[80%]">
            <div className="bg-emerald-600/15 border border-emerald-600/30 rounded-2xl px-4 py-2.5 text-sm text-foreground flex flex-col gap-2">
              {msg.attachments && msg.attachments.length > 0 && (
                <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
                  {msg.attachments.map((att) => (
                    <button
                      key={att.attachment_id}
                      type="button"
                      onClick={() => setLightboxSrc(att.preview_base64)}
                      className="rounded-lg overflow-hidden border border-emerald-600/20 hover:opacity-80 transition-opacity"
                      title={att.file_name}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={att.preview_base64}
                        alt={att.file_name}
                        className="w-full h-24 object-cover"
                      />
                    </button>
                  ))}
                </div>
              )}
              {msg.datasetAttachment && (
                <a
                  href={
                    msg.datasetAttachment.status === "ready"
                      ? `/datasets/view?id=${msg.datasetAttachment.dataset_id}`
                      : undefined
                  }
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`flex items-center gap-2 px-3 py-2 bg-background/40 border border-emerald-600/20 rounded-lg ${
                    msg.datasetAttachment.status === "ready"
                      ? "hover:bg-background/60 cursor-pointer"
                      : "cursor-default"
                  }`}
                >
                  <FileSpreadsheet size={16} className="text-emerald-400 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium truncate">
                      {msg.datasetAttachment.filename}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {msg.datasetAttachment.row_count ?? "?"} lignes ·{" "}
                      {msg.datasetAttachment.column_count ?? "?"} colonnes
                    </p>
                  </div>
                  {msg.datasetAttachment.status === "ready" && (
                    <span className="flex items-center gap-1 text-[11px] text-emerald-400 flex-shrink-0">
                      Ouvrir <ExternalLink size={11} />
                    </span>
                  )}
                </a>
              )}
              {msg.text && <span>{msg.text}</span>}
            </div>
            <div className="mt-0.5 p-1.5 bg-muted rounded-full flex-shrink-0">
              <User size={14} className="text-muted-foreground" />
            </div>
          </div>

          {lightboxSrc && (
            <div
              data-testid="image-lightbox"
              className="fixed inset-0 z-[100] flex items-center justify-center bg-black/85 p-8"
              onClick={() => setLightboxSrc(null)}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={lightboxSrc}
                alt="Image agrandie"
                className="max-w-full max-h-full rounded-lg shadow-2xl"
              />
              <button
                type="button"
                onClick={() => setLightboxSrc(null)}
                className="absolute top-6 right-6 p-2 bg-card/80 hover:bg-muted rounded-full text-foreground"
                title="Fermer"
              >
                <X size={18} />
              </button>
            </div>
          )}
        </div>
      );

    case "agent":
  return (
    <div className="flex justify-start">
      <div className="flex items-start gap-2 max-w-[80%]">
        <div className="mt-0.5 p-1.5 bg-emerald-600/15 rounded-full flex-shrink-0">
          <Bot size={14} className="text-emerald-400" />
        </div>
        <div
          data-testid="assistant-message"
          className="group bg-card border border-border rounded-2xl px-4 py-3 text-sm text-foreground flex flex-col gap-3 min-w-0 flex-1"
        >
          {/* Texte de la réponse (streaming ou complet) */}
          {msg.text ? (
            <MarkdownRenderer content={msg.text} className="text-sm" />
          ) : (
            <span className="text-muted-foreground italic">Vector réfléchit…</span>
          )}

          {/* Bouton dashboard (agent classique) */}
          {msg.datasetId && (
            <a
              href={`/dashboard?id=${msg.datasetId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-600/10 hover:bg-emerald-600/20 border border-emerald-600/30 text-emerald-400 text-xs font-medium self-start transition"
            >
              <ExternalLink size={13} />
              Ouvrir le dashboard
            </a>
          )}

          {/* Sources RAG */}
          {msg.sources && msg.sources.length > 0 && (
            <div className="mt-1 border-t border-border pt-3">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                📄 Sources ({msg.sources.length})
              </p>
              <div className="flex flex-col gap-2">
                {msg.sources.map((source, index) => (
                  <SourceCard
                    key={source.chunk_id || `source-${msg.id}-${index}`}
                    source={source}
                    index={index}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Sources web (J41.B) */}
          {msg.webSources && msg.webSources.length > 0 && (
            <div className="mt-1 border-t border-border pt-3">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                🌐 Sources web ({msg.webSources.length})
              </p>
              <div className="flex flex-col gap-2">
                {msg.webSources.map((source, index) => (
                  <WebSourceCard key={source.url + index} source={source} index={index} />
                ))}
              </div>
            </div>
          )}

          {/* Actions post-réponse : régénérer / copier / feedback */}
          {msg.text && (
            <MessageActions
              messageId={msg.id}
              messageText={msg.text}
              currentFeedback={msg.feedback ?? null}
              onRegenerate={() => onRegenerate(msg.id)}
              onFeedbackChange={(fb) => onFeedbackChange(msg.id, fb)}
              disabled={loading}
            />
          )}

          {/* Compteur de tokens/cout (J41+ Feature 2) */}
          {msg.usage && (
            <p
              className="text-[11px] text-muted-foreground"
              title={`${msg.usage.promptTokens} tokens prompt + ${msg.usage.completionTokens} tokens completion`}
            >
              {msg.usage.totalTokens} tokens · {msg.usage.costUsd.toFixed(4)} USD
              {msg.usage.model ? ` · ${msg.usage.model}` : ""}
            </p>
          )}
        </div>
      </div>
    </div>
  );

    case "status": {
  const cleanText = msg.text ? msg.text.replace(
    /^[\u{2600}-\u{27BF}\u{1F300}-\u{1FAFF}\u{FE0F}\u{200D}]+\s*/u,
    "",
  ) : "";
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground pl-1">
      {msg.done ? ( //l'erreur est ici, msg.done est undefined
        <CheckCircle2 size={13} className="text-emerald-500 flex-shrink-0" />
      ) : (
        <Loader2 size={13} className="animate-spin flex-shrink-0" />
      )}
      <span className="truncate">{cleanText}</span>
    </div>
  );
}

    case "tool":
      return <ToolTraceBubble trace={msg.trace} />;
 
    case "pdf_attachment": {
  const pdf = msg.pdf;
  const isReady = pdf.status === "ready";
  const isError = pdf.status === "error";
  const isProcessing = !isReady && !isError;

  const unitLabel =
    pdf.fileType === "docx"
      ? " sections indexées"
      : pdf.fileType === "pptx"
      ? " slides indexées"
      : " pages indexées";

  const statusLabel = {
    uploaded: "Upload en cours…",
    parsing: "Extraction du texte…",
    chunking: "Découpage en segments…",
    embedding: "Indexation vectorielle…",
    ready: "Prêt · " + (pdf.pageCount ?? "?") + unitLabel,
    error: "Erreur d'ingestion",
  }[pdf.status];

  const sizeKb = Math.round(pdf.fileSize / 1024);
  const sizeLabel =
    sizeKb > 1024
      ? `${(sizeKb / 1024).toFixed(1)} Mo`
      : `${sizeKb} Ko`;

  return (
    <div className="flex justify-end">
      <div className="flex items-center gap-3 max-w-[80%] px-4 py-3 rounded-2xl border transition-colors bg-emerald-950/40 border-emerald-800/60">
        {/* Icône format (PDF/WORD) */}
        <div
          className={`w-10 h-10 rounded-lg ${getFileTypeColorClass(pdf.fileType)} flex items-center justify-center text-[10px] font-bold text-white shrink-0`}
        >
          {getFileTypeLabel(pdf.fileType)}
        </div>

        {/* Nom + statut */}
        <div className="flex flex-col min-w-0">
          <span className="text-sm font-medium text-emerald-50 truncate max-w-[240px]">
            {pdf.fileName}
          </span>
          <span className="text-xs text-emerald-200/70 flex items-center gap-1.5 mt-0.5">
            {isProcessing && (
              <Loader2 className="w-3 h-3 animate-spin" />
            )}
            {isReady && <CheckCircle2 className="w-3 h-3" />}
            {isError && <AlertCircle className="w-3 h-3" />}
            <span>{sizeLabel} · {statusLabel}</span>
          </span>
        </div>
      </div>
    </div>
  );
}
      
    case "form":
      return (
        <AgentForm
          action={msg.action}
          onSubmit={(payload) => onFormSubmit(msg.id, msg.action, payload)}
          onCancel={() => onFormCancel(msg.id)}
        />
      );

    default:
      return null;
  }
}

function ToolTraceBubble({ trace }: { trace: ToolCallTrace }) {
  const isError = trace.status === "error";

  return (
    <div
      className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs border ${
        isError
          ? "bg-red-950/30 border-red-900/40"
          : "bg-card/60 border-border/80"
      }`}
    >
      {isError ? (
        <AlertCircle size={12} className="text-red-400 flex-shrink-0 mt-0.5" />
      ) : (
        <Wrench size={12} className="text-muted-foreground flex-shrink-0 mt-0.5" />
      )}

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={isError ? "text-red-300 font-medium" : "text-muted-foreground font-medium"}>
            {trace.name}
          </span>
          <span className="text-[10px] text-muted-foreground">
            {formatDuration(trace.duration_ms)}
          </span>
        </div>
        {trace.result_summary && (
          <p className={`mt-0.5 ${isError ? "text-red-400/80" : "text-muted-foreground"}`}>
            {trace.result_summary}
          </p>
        )}
      </div>
    </div>
  );
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}