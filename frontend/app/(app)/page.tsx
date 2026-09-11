"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Globe, Mic, MicOff, Send, Loader2, Paperclip, X, ImageIcon, FileSpreadsheet } from "lucide-react";

import AgentChat from "@/components/agent_chat";
import { useAgentChat } from "@/lib/hooks/use-agent-chat";
import { HelpPanel } from "@/components/help_panel";
import { ChatStarterHints } from "@/components/chat_starter_hints";
import { useKeyboardShortcuts } from "@/lib/hooks/use-keyboard-shortcuts";
import { useSpeechRecognition } from "@/lib/hooks/use-speech-recognition";
import { useDiscussionsStore } from "@/lib/store/discussions";
import { ALLOWED_IMAGE_MIME, MAX_IMAGE_FILE_SIZE } from "@/lib/images";
import { PersonaSelector } from "@/components/persona-selector";

export default function VectorPage() {
  const {
    messages,
    loading,
    error,
    showActionForm,
    submitForm,
    cancelForm,
    runFreeText,
    attachPdf,
    clearError,
    updateFeedback,
    regenerateMessage,
    webSearchEnabled,
    setWebSearchEnabled,
    pendingImages,
    addPendingImage,
    removePendingImage,
    pendingDataset,
    addPendingDataset,
    removePendingDataset,
  } = useAgentChat();

  const addDiscussion = useDiscussionsStore((s) => s.addDiscussion);

  const [input, setInput] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatInputRef = useRef<HTMLInputElement | null>(null);

  // ============================================================
  // Dictée vocale (J41.C — Web Speech API)
  // ============================================================

  const {
    isListening,
    transcript,
    interimTranscript,
    isSupported: isSpeechSupported,
    error: speechError,
    start: startListening,
    stop: stopListening,
    reset: resetTranscript,
  } = useSpeechRecognition("fr-FR");

  // Ajoute le texte final reconnu a l'input au fur et a mesure
  useEffect(() => {
    if (transcript) {
      setInput((prev) => prev + transcript);
      resetTranscript();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transcript]);

  // Erreur de dictee (micro refuse, etc.) -> toast
  useEffect(() => {
    if (speechError) toast.error(speechError);
  }, [speechError]);

  function handleToggleMic() {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }

  function pickStarterHint(question: string) {
    setInput(question);
    chatInputRef.current?.focus();
  }

  // ============================================================
  // Raccourcis clavier globaux (J28.E)
  // ============================================================

  useKeyboardShortcuts([
    // Ctrl+Shift+O : nouvelle discussion
    {
      key: "o",
      ctrl: true,
      shift: true,
      callback: () => addDiscussion(),
    },
    // ? : afficher l'aide
    {
      key: "?",
      shift: true,
      callback: () => setHelpOpen(true),
    },
  ]);

  // ============================================================
  // Handlers
  // ============================================================

  const hasReadyImage = pendingImages.some((p) => p.status === "ready");
  const hasReadyDataset = pendingDataset?.status === "ready";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (isListening) stopListening();
    const trimmed = input.trim();
    if ((!trimmed && !hasReadyImage && !hasReadyDataset) || loading) return;
    runFreeText(trimmed);
    setInput("");
  }

  function handleAttachClick() {
    fileInputRef.current?.click();
  }

  const DOCX_MIME =
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  const PPTX_MIME =
    "application/vnd.openxmlformats-officedocument.presentationml.presentation";
  // Doit rester synchronise avec MAX_FILE_SIZE dans backend/app/services/documents.py
  const MAX_DOCUMENT_FILE_SIZE = 50 * 1024 * 1024; // 50 Mo
  // Doit rester synchronise avec MAX_FILE_SIZE dans backend/app/services/datasets.py
  const MAX_DATASET_FILE_SIZE = 100 * 1024 * 1024; // 100 Mo

  function handleIncomingFile(file: File) {
    const lowerName = file.name.toLowerCase();

    if (ALLOWED_IMAGE_MIME.includes(file.type)) {
      if (file.size > MAX_IMAGE_FILE_SIZE) {
        toast.error(
          `"${file.name}" est trop volumineuse (${(file.size / 1024 / 1024).toFixed(1)} Mo). La taille maximale est de 10 Mo.`,
        );
        return;
      }
      addPendingImage(file);
      return;
    }

    // CSV/Excel : cree automatiquement un dataset persiste (J41+ Feature 4)
    if (
      lowerName.endsWith(".csv") ||
      lowerName.endsWith(".xlsx") ||
      lowerName.endsWith(".xls")
    ) {
      if (file.size > MAX_DATASET_FILE_SIZE) {
        toast.error(
          `"${file.name}" est trop volumineux (${(file.size / 1024 / 1024).toFixed(1)} Mo). La taille maximale est de 100 Mo.`,
        );
        return;
      }
      addPendingDataset(file);
      return;
    }

    if (
      file.type === "application/pdf" ||
      lowerName.endsWith(".pdf") ||
      file.type === DOCX_MIME ||
      lowerName.endsWith(".docx") ||
      file.type === PPTX_MIME ||
      lowerName.endsWith(".pptx")
    ) {
      if (file.size > MAX_DOCUMENT_FILE_SIZE) {
        toast.error(
          `"${file.name}" est trop volumineux (${(file.size / 1024 / 1024).toFixed(1)} Mo). La taille maximale est de 50 Mo.`,
        );
        return;
      }
      attachPdf(file);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files) return;
    Array.from(files).forEach(handleIncomingFile);
    e.target.value = "";
  }

  // Drag-and-drop d'images (et documents) directement sur la zone de chat
  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    if (e.dataTransfer.types.includes("Files")) setIsDraggingFile(true);
  }
  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    if (e.currentTarget === e.target) setIsDraggingFile(false);
  }
  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDraggingFile(false);
    Array.from(e.dataTransfer.files).forEach(handleIncomingFile);
  }

  // Détecte s'il y a un PDF ready dans la conversation (pour l'indicateur du bas)
  const hasReadyPdf = messages.some(
    (m) => m.kind === "pdf_attachment" && m.pdf.status === "ready",
  );
  const readyPdfCount = messages.filter(
    (m) => m.kind === "pdf_attachment" && m.pdf.status === "ready",
  ).length;

  return (
    <>
      <div
        className="relative flex flex-col h-full overflow-hidden"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
          {/* Overlay visuel pendant un drag de fichier */}
          {isDraggingFile && (
            <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/90 border-4 border-dashed border-emerald-500 pointer-events-none">
              <div className="flex flex-col items-center gap-3 text-emerald-400">
                <ImageIcon size={40} />
                <p className="text-lg font-semibold">Dépose ton image ou document ici</p>
              </div>
            </div>
          )}
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-5xl mx-auto px-8 py-10">
              {/* Bandeau de bienvenue */}
              <div className="text-center mb-12">
                <h1 className="text-5xl font-bold text-foreground mb-3 tracking-tight">
                  Commando IA{" "}
                  <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
                    Vector
                  </span>
                </h1>
                <p className="text-xl italic text-muted-foreground mb-3">
                  à votre service !
                </p>
                <p className="text-sm text-muted-foreground">
                  Quelle est la mission aujourd&apos;hui ?
                </p>
              </div>

              {/* Actions rapides + conversation */}
              <AgentChat
                messages={messages}
                loading={loading}
                error={error}
                onActionClick={showActionForm}
                onFormSubmit={submitForm}
                onFormCancel={cancelForm}
                onClearError={clearError}
                onRegenerate={regenerateMessage}
                onFeedbackChange={updateFeedback}
              />

              {/* Guide inline "comment poser une bonne question" — uniquement
                  si la conversation est vide et que l'user ne tape pas encore */}
              {messages.length === 0 && input.trim() === "" && (
                <ChatStarterHints onPick={pickStarterHint} />
              )}
            </div>
          </div>

          {/* Barre de saisie en bas */}
          <div className="border-t border-border bg-background flex-shrink-0">
            <div className="max-w-5xl mx-auto px-8 py-4">
              <div className="flex items-center gap-3 mb-3">
                <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">
                  Chat live
                </p>
                <PersonaSelector messageCount={messages.length} />
                {webSearchEnabled && (
                  <span className="flex items-center gap-1 text-xs text-emerald-400">
                    <Globe size={12} />
                    Recherche web activée
                  </span>
                )}
              </div>

              {/* Pieces jointes image en attente d'envoi (J41+ Feature 3) */}
              {pendingImages.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {pendingImages.map((pi) => (
                    <div
                      key={pi.id}
                      className="relative w-16 h-16 rounded-lg overflow-hidden border border-border bg-card flex-shrink-0"
                      title={pi.fileName}
                    >
                      {pi.status === "uploading" && (
                        <div className="absolute inset-0 flex items-center justify-center bg-card/80">
                          <Loader2 size={16} className="animate-spin text-emerald-400" />
                        </div>
                      )}
                      {pi.status === "error" && (
                        <div className="absolute inset-0 flex items-center justify-center bg-red-950/60 text-red-400 text-[10px] p-1 text-center">
                          Erreur
                        </div>
                      )}
                      {pi.attachment && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={pi.attachment.preview_base64}
                          alt={pi.fileName}
                          className="w-full h-full object-cover"
                        />
                      )}
                      <button
                        type="button"
                        onClick={() => removePendingImage(pi.id)}
                        className="absolute top-0.5 right-0.5 p-0.5 bg-background/80 hover:bg-red-600 rounded-full text-foreground hover:text-white transition-colors"
                        title="Retirer cette image"
                      >
                        <X size={11} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Dataset (CSV/Excel) en attente d'envoi (J41+ Feature 4) */}
              {pendingDataset && (
                <div className="flex items-center gap-2 mb-3 px-3 py-2 bg-card border border-border rounded-lg w-fit max-w-full">
                  {pendingDataset.status === "uploading" || pendingDataset.status === "profiling" ? (
                    <Loader2 size={15} className="animate-spin text-emerald-400 flex-shrink-0" />
                  ) : pendingDataset.status === "error" ? (
                    <FileSpreadsheet size={15} className="text-red-400 flex-shrink-0" />
                  ) : (
                    <FileSpreadsheet size={15} className="text-emerald-400 flex-shrink-0" />
                  )}
                  <div className="min-w-0">
                    <p className="text-xs text-foreground truncate">{pendingDataset.fileName}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {pendingDataset.status === "uploading" && "Envoi en cours..."}
                      {pendingDataset.status === "profiling" && "Analyse des colonnes..."}
                      {pendingDataset.status === "ready" &&
                        `${pendingDataset.rowCount ?? "?"} lignes · ${pendingDataset.columnCount ?? "?"} colonnes`}
                      {pendingDataset.status === "error" && (pendingDataset.error ?? "Erreur")}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={removePendingDataset}
                    className="p-1 hover:bg-red-600/20 rounded-full text-muted-foreground hover:text-red-400 transition-colors flex-shrink-0"
                    title="Retirer ce fichier"
                  >
                    <X size={13} />
                  </button>
                </div>
              )}

              <form
                onSubmit={handleSubmit}
                data-tour="chat-input"
                className="flex items-center gap-2 bg-card border border-border focus-within:border-emerald-500/60 rounded-2xl px-4 py-2 transition-colors"
              >
                {/* Input file caché */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx,application/vnd.openxmlformats-officedocument.presentationml.presentation,.pptx,image/png,image/jpeg,image/webp,image/gif,.csv,.xlsx,.xls"
                  multiple
                  onChange={handleFileChange}
                  className="hidden"
                />

                {/* Bouton attach PDF / Word / PowerPoint / Image / CSV / Excel */}
                <button
                  type="button"
                  data-tour="attach-button"
                  onClick={handleAttachClick}
                  className="p-2 hover:bg-emerald-600/10 border border-transparent hover:border-emerald-600/30 rounded-lg text-muted-foreground hover:text-emerald-400 transition-colors"
                  title="Joindre un document, une image ou un fichier de données (CSV/Excel)"
                >
                  <Paperclip size={16} />
                </button>

                <input
                  ref={chatInputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={
                    hasReadyPdf
                      ? "Poser une question sur le PDF..."
                      : "Poser une question à Vector..."
                  }
                  disabled={loading}
                  className="flex-1 bg-transparent text-sm text-foreground placeholder-muted-foreground focus:outline-none disabled:opacity-50"
                />

                <button
                  type="button"
                  onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                  className={
                    webSearchEnabled
                      ? "flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/40 rounded-lg text-xs text-emerald-400 transition-colors"
                      : "flex items-center gap-1.5 px-3 py-1.5 bg-transparent hover:bg-muted border border-transparent rounded-lg text-xs text-muted-foreground transition-colors"
                  }
                  title={
                    webSearchEnabled
                      ? "Désactiver la recherche web"
                      : "Activer la recherche web pour cette question"
                  }
                  aria-pressed={webSearchEnabled}
                >
                  <Globe size={14} />
                  Web
                </button>

                <button
                  type="button"
                  onClick={handleToggleMic}
                  disabled={!isSpeechSupported}
                  className={
                    isListening
                      ? "p-2 bg-red-500/10 border border-red-500/40 rounded-lg text-red-500 animate-pulse transition-colors"
                      : "p-2 hover:bg-muted rounded-lg text-muted-foreground transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  }
                  title={
                    !isSpeechSupported
                      ? "Recherche vocale non supportée par ce navigateur"
                      : isListening
                      ? "Arrêter la dictée"
                      : "Dicter la question au micro"
                  }
                  aria-pressed={isListening}
                >
                  {isListening ? <MicOff size={16} /> : <Mic size={16} />}
                </button>

                <button
                  type="submit"
                  disabled={loading || (!input.trim() && !hasReadyImage && !hasReadyDataset)}
                  className="p-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
                  title="Envoyer"
                >
                  {loading ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Send size={16} />
                  )}
                </button>
              </form>

              {/* Texte en cours de dictee (pas encore final) */}
              {isListening && interimTranscript && (
                <p className="mt-1.5 text-xs text-muted-foreground italic opacity-60">
                  {interimTranscript}
                </p>
              )}

              <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                <span
                  className={`inline-block w-1.5 h-1.5 rounded-full ${
                    isListening
                      ? "bg-red-500 animate-pulse"
                      : loading
                      ? "bg-amber-500 animate-pulse"
                      : "bg-emerald-500"
                  }`}
                />
                {isListening ? (
                  <span className="text-red-400">Écoute en cours...</span>
                ) : loading ? (
                  hasReadyPdf ? (
                    "Vector cherche dans le PDF..."
                  ) : (
                    "Vector réfléchit..."
                  )
                ) : hasReadyPdf ? (
                  `Prêt · ${readyPdfCount} PDF ${readyPdfCount > 1 ? "actifs" : "actif"} dans la conversation`
                ) : (
                  "Prêt"
                )}
              </div>
            </div>
          </div>
        </div>

      {/* ============================================================
          Panneau d'aide (raccourcis clavier) — J28.E
          ============================================================ */}
      <HelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} />
    </>
  );
}