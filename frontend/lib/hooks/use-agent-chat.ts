"use client";

import { useCallback, useEffect, useState } from "react";

import {
  appendMessage,
  generateConversationTitle,
  getConversation,
} from "@/lib/conversations";
import { useDiscussionsStore } from "@/lib/store/discussions";
import {
  agentChat,
  agentRunTool,
  type ToolCallTrace,
} from "@/lib/agent";
import type { QuickAction } from "@/lib/quick_actions";
import {
  uploadDataset,
  pollDatasetReady,
  getDataset,
} from "@/lib/datasets";
import {
  uploadDocument,
  pollDocumentReady,
  getFileTypeFromName,
  type DocumentStatus,
  type FileType,
} from "@/lib/documents";
import { streamRagAnswer, type RagSource } from "@/lib/rag";
import { streamCorpusRagAnswer } from "@/lib/corpus";
import { streamWebSearchAnswer, type WebSource } from "@/lib/web_search";
import {
  resizeImageIfNeeded,
  uploadImageAttachment,
  type ImageAttachmentPayload,
} from "@/lib/images";
import type { FormSubmitPayload } from "@/components/agent_form";
import { useAuthStore } from "@/lib/store/auth";
import { ApiError } from "@/lib/api";
import {
  deleteMessage,
  updateMessageFeedback,
  type MessageFeedback,
} from "@/lib/messages";
import { toast } from "sonner";

// ============================================================
// Types
// ============================================================

/**
 * PDF attaché dans une bulle de conversation.
 * `documentId` peut être null pendant l'upload initial (avant que le backend
 * ait retourné l'id). Il est ensuite rempli avec le vrai UUID.
 */
export type AttachedPdfInMessage = {
  documentId: string | null;
  fileName: string;
  fileSize: number;
  fileType: FileType;
  status: DocumentStatus;
  pageCount: number | null;
};

// NEW J41+ Feature 2 — compteur de tokens/cout affiche sous chaque reponse
export type MessageUsage = {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  costUsd: number;
  model: string;
};

// NEW J41+ Feature 3 — image en cours d'upload avant envoi du message
export type PendingImage = {
  id: string;
  fileName: string;
  status: "uploading" | "ready" | "error";
  attachment?: ImageAttachmentPayload;
  error?: string;
};

// NEW J41+ Feature 4 — dataset (CSV/Excel) joint a un message de chat
export type DatasetAttachmentPayload = {
  type: "dataset";
  dataset_id: string;
  filename: string;
  status: string;
  row_count?: number | null;
  column_count?: number | null;
};

export type PendingDataset = {
  id: string;
  fileName: string;
  status: "uploading" | "profiling" | "ready" | "error";
  datasetId?: string;
  rowCount?: number | null;
  columnCount?: number | null;
  error?: string;
};

export type AgentMessage =
  | {
      id: string;
      kind: "user";
      text: string;
      attachments?: ImageAttachmentPayload[];
      datasetAttachment?: DatasetAttachmentPayload;
    }
  | { id: string; kind: "form"; action: QuickAction }
  | { id: string; kind: "status"; text: string; done?: boolean }
  | { id: string; kind: "tool"; trace: ToolCallTrace }
  | { id: string; kind: "pdf_attachment"; pdf: AttachedPdfInMessage }
  | {
      id: string;
      kind: "agent";
      text: string;
      datasetId?: string;
      sources?: RagSource[];
      webSources?: WebSource[];
      feedback?: MessageFeedback;
      usage?: MessageUsage;
    };

// ============================================================
// Helpers
// ============================================================

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

let _msgId = 0;
const nextId = () => `m_${++_msgId}_${Date.now()}`;

/**
 * Fire-and-forget : demande au backend de generer un titre si c'est le
 * premier echange complet. Best-effort, ne doit jamais afficher d'erreur
 * a l'user (nice-to-have, pas critique).
 */
function triggerTitleGeneration(conversationId: string, token: string): void {
  if (conversationId.startsWith("temp_")) return;
  generateConversationTitle(token, conversationId)
    .then((updated) => {
      useDiscussionsStore.getState().updateDiscussionTitle(conversationId, updated.title);
    })
    .catch((err) => {
      console.warn("[use-agent-chat] generation de titre echouee (silencieux) :", err);
    });
}

// ============================================================
// Hook principal
// ============================================================

export function useAgentChat() {
  const token = useAuthStore((s) => s.token);

  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [pendingImages, setPendingImages] = useState<PendingImage[]>([]);
  const [pendingDataset, setPendingDataset] = useState<PendingDataset | null>(null);

  // ============================================================
  // Sync avec le store discussions (J25.B)
  // ============================================================

  const activeId = useDiscussionsStore((s) => s.activeId);
  const setToken = useDiscussionsStore((s) => s.setToken);
  const loadFromBackend = useDiscussionsStore((s) => s.loadFromBackend);
  const bumpUpdatedAt = useDiscussionsStore((s) => s.bumpUpdatedAt);

  // Setup le token dans le store discussions
  useEffect(() => {
    setToken(token);
  }, [token, setToken]);

  // Load initial des conversations au montage
  useEffect(() => {
    if (!token) return;
    loadFromBackend(token);
  }, [token, loadFromBackend]);

  // Load des messages quand activeId change (switch de conversation)
  useEffect(() => {
    if (!activeId || !token) {
      setMessages([]);
      return;
    }

    // Skip si tempId (conv pas encore créée backend)
    if (activeId.startsWith("temp_")) {
      setMessages([]);
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const conv = await getConversation(token, activeId);
        if (cancelled) return;

        // Reconstruit les AgentMessage depuis les MessageResponse backend
        const rehydrated: AgentMessage[] = conv.messages.map((m) => {
          switch (m.message_kind) {
            case "user": {
              const allAttachments = (m.attachments as
                | Array<Record<string, unknown>>
                | null) ?? [];
              const images = allAttachments.filter(
                (a) => a.type === "image",
              ) as unknown as ImageAttachmentPayload[];
              const datasetAtt = allAttachments.find(
                (a) => a.type === "dataset",
              ) as unknown as DatasetAttachmentPayload | undefined;
              return {
                id: m.id,
                kind: "user",
                text: m.content,
                attachments: images.length > 0 ? images : undefined,
                datasetAttachment: datasetAtt,
              };
            }
            case "status":
              return { id: m.id, kind: "status", text: m.content, done: true };
            case "tool":
              return {
                id: m.id,
                kind: "tool",
                trace: (m.tool_calls?.[0] ?? {
                  tool: "unknown",
                  status: "success",
                  duration_ms: 0,
                }) as ToolCallTrace,
              };
            case "pdf_attachment":
              return {
                id: m.id,
                kind: "pdf_attachment",
                pdf: {
                  documentId: (m.extra_data?.document_id as string) ?? null,
                  fileName: (m.extra_data?.file_name as string) ?? "Document",
                  fileSize: (m.extra_data?.file_size as number) ?? 0,
                  fileType: getFileTypeFromName(
                    (m.extra_data?.file_name as string) ?? "",
                  ),
                  status: "ready",
                  pageCount:
                    (m.extra_data?.page_count as number | null) ?? null,
                },
              };
            case "agent":
            default: {
              // Les sources web (WebSource: title/url/snippet, sans chunk_id)
              // partagent la meme colonne DB "sources" que les sources RAG
              // (RagSource: chunk_id/document_id/...). On les distingue a la
              // rehydratation par la presence de chunk_id, pour les router
              // vers le bon champ (sources vs webSources) et donc le bon
              // composant de rendu (SourceCard vs WebSourceCard) — sinon
              // key={source.chunk_id} vaut undefined pour chaque source web
              // rechargee (warning React "unique key prop").
              const rawSources =
                (m.sources as Array<Record<string, unknown>> | null) ?? null;
              const isWebSources =
                !!rawSources && rawSources.length > 0 && !("chunk_id" in rawSources[0]);

              return {
                id: m.id,
                kind: "agent",
                text: m.content,
                sources: !isWebSources
                  ? ((rawSources as RagSource[] | null) ?? undefined)
                  : undefined,
                webSources: isWebSources
                  ? (rawSources as unknown as WebSource[])
                  : undefined,
                datasetId:
                  (m.extra_data?.dataset_id as string | undefined) ?? undefined,
                feedback: (m.feedback as MessageFeedback) ?? null,
                usage:
                  m.total_tokens != null
                    ? {
                        promptTokens: m.prompt_tokens ?? 0,
                        completionTokens: m.completion_tokens ?? 0,
                        totalTokens: m.total_tokens,
                        costUsd: m.cost_usd ?? 0,
                        model: m.model_used ?? "",
                      }
                    : undefined,
              };
            }
          }
        });

        setMessages(rehydrated);
      } catch (err) {
        console.error("[use-agent-chat] load conv erreur :", err);
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Erreur de chargement");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [activeId, token]);

  // ============================================================
  // Helper — sauve un message backend (skip si tempId)
  // ============================================================

  const persistMessage = useCallback(
    async (
      conversationId: string,
      role: string,
      message_kind: string,
      content: string,
      extras: {
        tool_calls?: unknown[] | null;
        sources?: unknown[] | null;
        extra_data?: Record<string, unknown> | null;
        usage?: MessageUsage | null;
        attachments?: Array<ImageAttachmentPayload | DatasetAttachmentPayload> | null;
      } = {},
    ) => {
      if (!token) return null;
      if (conversationId.startsWith("temp_")) return null;

      try {
        const saved = await appendMessage(token, conversationId, {
          role,
          message_kind,
          content,
          tool_calls: extras.tool_calls ?? null,
          sources: extras.sources ?? null,
          extra_data: extras.extra_data ?? null,
          prompt_tokens: extras.usage?.promptTokens ?? null,
          completion_tokens: extras.usage?.completionTokens ?? null,
          total_tokens: extras.usage?.totalTokens ?? null,
          cost_usd: extras.usage?.costUsd ?? null,
          model_used: extras.usage?.model ?? null,
          attachments: extras.attachments as Record<string, unknown>[] | null | undefined,
        });
        bumpUpdatedAt(conversationId);

        // Titre auto-genere (J41+ Feature 1) : fire-and-forget apres chaque
        // reponse Vector complete. Le backend est la source de verite pour
        // savoir si c'est reellement le premier echange et si le titre est
        // encore le defaut — idempotent, donc pas besoin de compter les
        // messages cote client (fragile avec l'etat React asynchrone).
        if (role === "assistant" && message_kind === "agent" && token) {
          triggerTitleGeneration(conversationId, token);
        }

        return saved;
      } catch (err) {
        console.error("[use-agent-chat] persistMessage erreur :", err);
        return null;
      }
    },
    [token, bumpUpdatedAt],
  );

  // ============================================================
  // Helper — remplace l'id local (nextId()) d'un message agent par
  // le vrai UUID backend une fois la persistance confirmée.
  // Indispensable pour que feedback/régénération (qui ciblent l'id
  // backend) fonctionnent sur une réponse fraîchement générée.
  // ============================================================

  const reconcileAgentId = useCallback(
    (localId: string, backendId: string | undefined) => {
      if (!backendId || backendId === localId) return;
      setMessages((m) =>
        m.map((msg) =>
          msg.id === localId && msg.kind === "agent"
            ? { ...msg, id: backendId }
            : msg,
        ),
      );
    },
    [],
  );

  // ============================================================
  // Helper — met à jour une bulle PDF (par id de message)
  // ============================================================

  const updatePdfMessage = useCallback(
    (messageId: string, patch: Partial<AttachedPdfInMessage>) => {
      setMessages((m) =>
        m.map((msg) =>
          msg.id === messageId && msg.kind === "pdf_attachment"
            ? { ...msg, pdf: { ...msg.pdf, ...patch } }
            : msg,
        ),
      );
    },
    [],
  );

  // ============================================================
  // Helper — trouve le PDF ready le plus récent dans la conversation
  // ============================================================

  const getActivePdfDocumentId = useCallback((): string | null => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (
        msg.kind === "pdf_attachment" &&
        msg.pdf.status === "ready" &&
        msg.pdf.documentId
      ) {
        return msg.pdf.documentId;
      }
    }
    return null;
  }, [messages]);

  // ============================================================
  // Helper — resout le scope RAG de la conversation active (J34)
  //
  // Priorite 1 : document_id / corpus_id stocke sur la conversation
  // elle-meme (cree via "Poser une question" sur un doc, ou "Interroger
  // ce corpus" sur un corpus). C'etait un angle mort avant J34 : seul le
  // scan des bulles pdf_attachment ci-dessus etait utilise, donc une conv
  // creee directement avec document_id (sans bulle pdf_attachment dans
  // l'historique) tombait a tort sur l'agent classique au lieu du RAG.
  //
  // Priorite 2 (fallback) : PDF attache en cours de conversation via le
  // trombone (flow chat classique, pas de corpus_id/document_id sur la
  // conv elle-meme dans ce cas).
  // ============================================================

  const getActiveScopedIds = useCallback((): {
    documentId: string | null;
    corpusId: string | null;
  } => {
    const activeDiscussion = useDiscussionsStore
      .getState()
      .discussions.find((d) => d.id === activeId);

    if (activeDiscussion?.corpusId) {
      return { documentId: null, corpusId: activeDiscussion.corpusId };
    }
    if (activeDiscussion?.documentId) {
      return { documentId: activeDiscussion.documentId, corpusId: null };
    }

    return { documentId: getActivePdfDocumentId(), corpusId: null };
  }, [activeId, getActivePdfDocumentId]);

  // ============================================================
  // Attach PDF (UX ChatGPT-like)
  // ============================================================

  const attachPdf = useCallback(
    async (file: File) => {
      if (!token) return;
      setError(null);

      // 1. Crée immédiatement une bulle utilisateur avec la pastille PDF
      const pdfMessageId = nextId();
      setMessages((m) => [
        ...m,
        {
          id: pdfMessageId,
          kind: "pdf_attachment",
          pdf: {
            documentId: null,
            fileName: file.name,
            fileSize: file.size,
            fileType: getFileTypeFromName(file.name),
            status: "uploaded",
            pageCount: null,
          },
        },
      ]);

      try {
        // 2. Upload effectif
        const uploaded = await uploadDocument(token, file, file.name);
        updatePdfMessage(pdfMessageId, {
          documentId: uploaded.id,
          status: uploaded.status,
        });

        // 3. Poll jusqu'à ready avec update visuel du status
        await pollDocumentReady(uploaded.id, token, {
          maxAttempts: 60,
          intervalMs: 2000,
          onProgress: (status) => {
            updatePdfMessage(pdfMessageId, { status });
          },
        });

        // 4. Récupère les métadonnées finales (page_count)
        const { fetchDocument } = await import("@/lib/documents");
        const detail = await fetchDocument(token, uploaded.id);
        updatePdfMessage(pdfMessageId, {
          status: "ready",
          pageCount: detail.page_count,
        });

        // 5. Persister la bulle PDF en backend
        if (activeId) {
          await persistMessage(
            activeId,
            "user",
            "pdf_attachment",
            file.name,
            {
              extra_data: {
                document_id: uploaded.id,
                file_name: file.name,
                file_size: file.size,
                page_count: detail.page_count,
              },
            },
          );
        }

        // 6. Accusé de réception Vector automatique
        await sleep(300);
        const pageInfo = detail.page_count
          ? `${detail.page_count} pages indexées`
          : "document indexé";
        const ackText =
          `✓ J'ai bien reçu **${file.name}**. ${pageInfo}, ` +
          `prêtes à être interrogées. Que veux-tu savoir ?`;
        const ackLocalId = nextId();
        setMessages((m) => [
          ...m,
          {
            id: ackLocalId,
            kind: "agent",
            text: ackText,
          },
        ]);

        // 7. Persister l'accusé de réception en backend
        if (activeId) {
          const saved = await persistMessage(
            activeId,
            "assistant",
            "agent",
            ackText,
          );
          reconcileAgentId(ackLocalId, saved?.id);
        }
      } catch (e: unknown) {
        const msg =
          e instanceof ApiError
            ? e.detail
            : e instanceof Error
            ? e.message
            : "Erreur d'upload PDF";
        setError(msg);
        updatePdfMessage(pdfMessageId, { status: "error" });
      }
    },
    [token, activeId, updatePdfMessage, persistMessage, reconcileAgentId],
  );

  // ============================================================
  // Actions rapides — formulaires (inchangé J19)
  // ============================================================

  const showActionForm = useCallback((action: QuickAction) => {
    setError(null);
    setMessages((m) => [
      ...m,
      { id: nextId(), kind: "form", action },
    ]);
  }, []);

  const cancelForm = useCallback((messageId: string) => {
    setMessages((m) => m.filter((msg) => msg.id !== messageId));
  }, []);

  const submitForm = useCallback(
    async (
      messageId: string,
      action: QuickAction,
      payload: FormSubmitPayload,
    ) => {
      if (!token) return;
      setError(null);

      setMessages((m) =>
        m.map((msg) =>
          msg.id === messageId
            ? { id: messageId, kind: "user", text: payload.humanSummary }
            : msg,
        ),
      );

      // Persistance du message user backend
      if (activeId) {
        await persistMessage(activeId, "user", "user", payload.humanSummary);
      }

      setLoading(true);
      try {
        let datasetId = payload.datasetId;

        if (payload.file) {
          const uploadStatusId = nextId();
          setMessages((m) => [
            ...m,
            {
              id: uploadStatusId,
              kind: "status",
              text: "📤 Upload du fichier en cours…",
            },
          ]);

          const uploaded = await uploadDataset(
            token,
            payload.file,
            payload.file.name,
          );
          datasetId = uploaded.id;

          setMessages((m) =>
            m.map((msg) =>
              msg.id === uploadStatusId && msg.kind === "status"
                ? {
                    ...msg,
                    text: `✅ Fichier uploadé : ${payload.file!.name}`,
                    done: true,
                  }
                : msg,
            ),
          );

          const profileStatusId = nextId();
          setMessages((m) => [
            ...m,
            {
              id: profileStatusId,
              kind: "status",
              text: "🔍 Profilage du dataset (colonnes, types, qualité)…",
            },
          ]);

          await pollDatasetReady(datasetId, token, {
            maxAttempts: 30,
            intervalMs: 1000,
          });

          setMessages((m) =>
            m.map((msg) =>
              msg.id === profileStatusId && msg.kind === "status"
                ? { ...msg, text: "✅ Profilage terminé", done: true }
                : msg,
            ),
          );
        }

        if (!datasetId) {
          throw new Error("Aucun dataset_id disponible après l'upload");
        }

        const genStatusId = nextId();
        setMessages((m) => [
          ...m,
          {
            id: genStatusId,
            kind: "status",
            text: `📊 Génération du ${action.title.toLowerCase()}…`,
          },
        ]);

        const res = await agentRunTool(
          action.toolName,
          { dataset_id: datasetId, ...payload.extraParams },
          token,
        );

        setMessages((m) =>
          m.map((msg) =>
            msg.id === genStatusId && msg.kind === "status"
              ? { ...msg, text: "✅ Dashboard généré", done: true }
              : msg,
          ),
        );

        for (const trace of res.tool_calls) {
          await sleep(300);
          setMessages((m) => [
            ...m,
            { id: nextId(), kind: "tool", trace },
          ]);
          // Persistance backend de la trace d'outil
          if (activeId) {
            await persistMessage(
              activeId,
              "assistant",
              "tool",
              trace.name ?? "tool",
              { tool_calls: [trace as unknown as Record<string, unknown>] },
            );
          }
        }

        await sleep(250);
        const finalDatasetId = res.artifacts?.dataset_id ?? datasetId;
        const formAgentLocalId = nextId();
        setMessages((m) => [
          ...m,
          {
            id: formAgentLocalId,
            kind: "agent",
            text: res.message,
            datasetId: finalDatasetId,
          },
        ]);

        // Persistance backend de la réponse Vector
        if (activeId) {
          const saved = await persistMessage(
            activeId,
            "assistant",
            "agent",
            res.message,
            {
              extra_data: finalDatasetId
                ? { dataset_id: finalDatasetId }
                : null,
            },
          );
          reconcileAgentId(formAgentLocalId, saved?.id);
        }
      } catch (e: unknown) {
        const msg =
          e instanceof ApiError
            ? e.detail
            : e instanceof Error
            ? e.message
            : "Erreur inconnue";
        setError(msg);
      } finally {
        setLoading(false);
      }
    },
    [token, activeId, persistMessage, reconcileAgentId],
  );

  // ============================================================
  // Free text — routing intelligent (RAG si PDF actif, sinon agent)
  // ============================================================

  const runFreeText = useCallback(
    async (text: string) => {
      if (loading || !token) return;
      setError(null);

      const trimmed = text.trim();
      const readyImages = pendingImages
        .filter((p) => p.status === "ready" && p.attachment)
        .map((p) => p.attachment!);
      const readyDataset: DatasetAttachmentPayload | null =
        pendingDataset?.status === "ready" && pendingDataset.datasetId
          ? {
              type: "dataset",
              dataset_id: pendingDataset.datasetId,
              filename: pendingDataset.fileName,
              status: "ready",
              row_count: pendingDataset.rowCount ?? null,
              column_count: pendingDataset.columnCount ?? null,
            }
          : null;
      if (!trimmed && readyImages.length === 0 && !readyDataset) return;

      // Resout le scope RAG de la conversation active (doc, corpus, ou aucun)
      const { documentId: activePdfId, corpusId: activeCorpusId } =
        getActiveScopedIds();

      // Affiche immédiatement le message user
      const userMsgId = nextId();
      setMessages((m) => [
        ...m,
        {
          id: userMsgId,
          kind: "user",
          text: trimmed,
          attachments: readyImages.length > 0 ? readyImages : undefined,
          datasetAttachment: readyDataset ?? undefined,
        },
      ]);
      setPendingImages([]);
      setPendingDataset(null);

      const allAttachments: Array<ImageAttachmentPayload | DatasetAttachmentPayload> = [
        ...readyImages,
        ...(readyDataset ? [readyDataset] : []),
      ];

      // Persistance backend du message user. Le titre auto (ex-troncature
      // brute des 60 premiers caracteres) est remplace par la generation LLM
      // (J41+ Feature 1), declenchee apres la reponse assistant complete —
      // voir triggerTitleGeneration dans persistMessage.
      if (activeId) {
        await persistMessage(activeId, "user", "user", trimmed, {
          attachments: allAttachments.length > 0 ? allAttachments : null,
        });
      }

      setLoading(true);

      try {
        if (webSearchEnabled) {
          await runWebSearchStream(trimmed);
        } else if (activeCorpusId) {
          await runCorpusRagStream(trimmed, activeCorpusId);
        } else if (activePdfId) {
          await runRagStream(trimmed, activePdfId);
        } else {
          await runAgentChat(trimmed, allAttachments);
        }
      } finally {
        // Garantit que loading redescend à false quoi qu'il arrive
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, loading, messages, activeId, webSearchEnabled, pendingImages, pendingDataset],
  );

  // ============================================================
  // Piece jointe dataset (CSV/Excel envoye dans le chat) — NEW J41+ Feature 4
  // ============================================================

  const addPendingDataset = useCallback(
    async (file: File) => {
      if (!token) return;
      if (pendingDataset && pendingDataset.status !== "error") {
        toast.error("Un seul fichier de données à la fois par message.");
        return;
      }

      const localId = nextId();
      setPendingDataset({ id: localId, fileName: file.name, status: "uploading" });

      try {
        const uploaded = await uploadDataset(token, file);
        setPendingDataset((p) =>
          p && p.id === localId
            ? { ...p, status: "profiling", datasetId: uploaded.id }
            : p,
        );

        await pollDatasetReady(uploaded.id, token, {
          maxAttempts: 60,
          intervalMs: 2000,
        });
        const detail = await getDataset(token, uploaded.id);

        setPendingDataset((p) =>
          p && p.id === localId
            ? {
                ...p,
                status: "ready",
                rowCount: detail.row_count,
                columnCount: detail.column_count,
              }
            : p,
        );
      } catch (e: unknown) {
        const msg =
          e instanceof ApiError
            ? e.detail
            : e instanceof Error
            ? e.message
            : "Erreur inconnue";
        setPendingDataset((p) =>
          p && p.id === localId ? { ...p, status: "error", error: msg } : p,
        );
        toast.error(`Fichier de données refusé : ${msg}`);
      }
    },
    [token, pendingDataset],
  );

  const removePendingDataset = useCallback(() => setPendingDataset(null), []);

  // ============================================================
  // Pieces jointes image (ChatGPT-like : upload immediat, jointes au
  // prochain message envoye) — NEW J41+ Feature 3
  // ============================================================

  const addPendingImage = useCallback(
    async (file: File) => {
      if (!token || !activeId || activeId.startsWith("temp_")) {
        toast.error("Attends que la conversation soit prête avant d'ajouter une image.");
        return;
      }

      const localId = nextId();
      setPendingImages((p) => [
        ...p,
        { id: localId, fileName: file.name, status: "uploading" },
      ]);

      try {
        const resized = await resizeImageIfNeeded(file);
        const attachment = await uploadImageAttachment(token, activeId, resized);
        setPendingImages((p) =>
          p.map((pi) =>
            pi.id === localId ? { ...pi, status: "ready", attachment } : pi,
          ),
        );
      } catch (e: unknown) {
        const msg =
          e instanceof ApiError
            ? e.detail
            : e instanceof Error
            ? e.message
            : "Erreur inconnue";
        setPendingImages((p) =>
          p.map((pi) =>
            pi.id === localId ? { ...pi, status: "error", error: msg } : pi,
          ),
        );
        toast.error(`Image refusée : ${msg}`);
      }
    },
    [token, activeId],
  );

  const removePendingImage = useCallback((id: string) => {
    setPendingImages((p) => p.filter((pi) => pi.id !== id));
  }, []);

  // ============================================================
  // Sous-fonction : agent chat classique
  // ============================================================

  const runAgentChat = useCallback(
    async (
      text: string,
      attachments?: Array<ImageAttachmentPayload | DatasetAttachmentPayload>,
    ) => {
      if (!token) return;
      try {
        const res = await agentChat(text, token, activeId, attachments);

        for (const trace of res.tool_calls) {
          await sleep(300);
          setMessages((m) => [
            ...m,
            { id: nextId(), kind: "tool", trace },
          ]);
          // Persistance backend
          if (activeId) {
            await persistMessage(
              activeId,
              "assistant",
              "tool",
              trace.name ?? "tool",
              { tool_calls: [trace as unknown as Record<string, unknown>] },
            );
          }
        }

        await sleep(250);
        const agentLocalId = nextId();
        const usage: MessageUsage | undefined =
          res.total_tokens != null
            ? {
                promptTokens: res.prompt_tokens ?? 0,
                completionTokens: res.completion_tokens ?? 0,
                totalTokens: res.total_tokens,
                costUsd: res.cost_usd ?? 0,
                model: res.model_used ?? "",
              }
            : undefined;
        setMessages((m) => [
          ...m,
          {
            id: agentLocalId,
            kind: "agent",
            text: res.message,
            datasetId: res.artifacts?.dataset_id,
            usage,
          },
        ]);

        // Persistance backend de la réponse
        if (activeId) {
          const saved = await persistMessage(
            activeId,
            "assistant",
            "agent",
            res.message,
            {
              extra_data: res.artifacts?.dataset_id
                ? { dataset_id: res.artifacts.dataset_id }
                : null,
              usage,
            },
          );
          reconcileAgentId(agentLocalId, saved?.id);
        }
      } catch (e: unknown) {
        const msg =
          e instanceof ApiError
            ? e.detail
            : e instanceof Error
            ? e.message
            : "Erreur inconnue";
        setError(msg);
      }
    },
    [token, activeId, persistMessage, reconcileAgentId],
  );

  // ============================================================
  // Sous-fonction : RAG streaming
  // ============================================================

  const runRagStream = useCallback(
    async (question: string, documentId: string) => {
      if (!token) return;

      const agentMsgId = nextId();
      let accumulated = "";
      let receivedSources: RagSource[] = [];
      let receivedUsage: MessageUsage | undefined;
      let streamCompleted = false;

      setMessages((m) => [
        ...m,
        {
          id: agentMsgId,
          kind: "agent",
          text: "",
          sources: [],
        },
      ]);

      try {
        await streamRagAnswer({
          question,
          documentId,
          token,
          topK: 5,
          callbacks: {
            onSources: (sources) => {
              receivedSources = sources;
              setMessages((m) =>
                m.map((msg) =>
                  msg.id === agentMsgId && msg.kind === "agent"
                    ? { ...msg, sources }
                    : msg,
                ),
              );
            },
            onToken: (tk) => {
              accumulated += tk;
              const snapshot = accumulated;
              setMessages((m) =>
                m.map((msg) =>
                  msg.id === agentMsgId && msg.kind === "agent"
                    ? { ...msg, text: snapshot }
                    : msg,
                ),
              );
            },
            onDone: (stats) => {
              streamCompleted = true;
              if (stats.total_tokens != null) {
                receivedUsage = {
                  promptTokens: stats.prompt_tokens ?? 0,
                  completionTokens: stats.completion_tokens ?? 0,
                  totalTokens: stats.total_tokens,
                  costUsd: stats.cost_usd ?? 0,
                  model: stats.model_used ?? "",
                };
                setMessages((m) =>
                  m.map((msg) =>
                    msg.id === agentMsgId && msg.kind === "agent"
                      ? { ...msg, usage: receivedUsage }
                      : msg,
                  ),
                );
              }
            },
            onError: (errMsg) => {
              setError(errMsg);
              setMessages((m) =>
                m.map((msg) =>
                  msg.id === agentMsgId && msg.kind === "agent"
                    ? {
                        ...msg,
                        text:
                          (msg.text || "") +
                          `\n\n**Erreur** : ${errMsg}`,
                      }
                    : msg,
                ),
              );
            },
          },
        });
      } catch (e: unknown) {
        const errMsg = e instanceof Error ? e.message : "Erreur inconnue";
        setError(errMsg);
      } finally {
        // Si aucun token n'est arrivé, on met un message d'erreur explicite
        if (!streamCompleted && accumulated === "") {
          setMessages((m) =>
            m.map((msg) =>
              msg.id === agentMsgId && msg.kind === "agent"
                ? {
                    ...msg,
                    text:
                      "Erreur : aucune réponse reçue du serveur. " +
                      "Vérifie que le backend RAG tourne et que le PDF est bien indexé.",
                  }
                : msg,
            ),
          );
        } else if (streamCompleted && accumulated.trim().length > 0) {
          // Persistance backend de la réponse RAG complète + sources
          if (activeId) {
            const saved = await persistMessage(
              activeId,
              "assistant",
              "agent",
              accumulated,
              {
                sources:
                  receivedSources.length > 0
                    ? (receivedSources as unknown as Record<string, unknown>[])
                    : null,
                usage: receivedUsage,
              },
            );
            reconcileAgentId(agentMsgId, saved?.id);
          }
        }
      }
    },
    [token, activeId, persistMessage, reconcileAgentId],
  );

  // ============================================================
  // Sous-fonction : RAG streaming multi-documents (corpus, J34)
  // ============================================================

  const runCorpusRagStream = useCallback(
    async (question: string, corpusId: string) => {
      if (!token) return;

      const agentMsgId = nextId();
      let accumulated = "";
      let receivedSources: RagSource[] = [];
      let receivedUsage: MessageUsage | undefined;
      let streamCompleted = false;

      setMessages((m) => [
        ...m,
        {
          id: agentMsgId,
          kind: "agent",
          text: "",
          sources: [],
        },
      ]);

      try {
        await streamCorpusRagAnswer({
          corpusId,
          question,
          token,
          topK: 8,
          callbacks: {
            onSources: (sources) => {
              receivedSources = sources;
              setMessages((m) =>
                m.map((msg) =>
                  msg.id === agentMsgId && msg.kind === "agent"
                    ? { ...msg, sources }
                    : msg,
                ),
              );
            },
            onToken: (tk) => {
              accumulated += tk;
              const snapshot = accumulated;
              setMessages((m) =>
                m.map((msg) =>
                  msg.id === agentMsgId && msg.kind === "agent"
                    ? { ...msg, text: snapshot }
                    : msg,
                ),
              );
            },
            onDone: (stats) => {
              streamCompleted = true;
              if (stats.total_tokens != null) {
                receivedUsage = {
                  promptTokens: stats.prompt_tokens ?? 0,
                  completionTokens: stats.completion_tokens ?? 0,
                  totalTokens: stats.total_tokens,
                  costUsd: stats.cost_usd ?? 0,
                  model: stats.model_used ?? "",
                };
                setMessages((m) =>
                  m.map((msg) =>
                    msg.id === agentMsgId && msg.kind === "agent"
                      ? { ...msg, usage: receivedUsage }
                      : msg,
                  ),
                );
              }
            },
            onError: (errMsg) => {
              setError(errMsg);
              setMessages((m) =>
                m.map((msg) =>
                  msg.id === agentMsgId && msg.kind === "agent"
                    ? {
                        ...msg,
                        text:
                          (msg.text || "") +
                          `\n\n**Erreur** : ${errMsg}`,
                      }
                    : msg,
                ),
              );
            },
          },
        });
      } catch (e: unknown) {
        const errMsg = e instanceof Error ? e.message : "Erreur inconnue";
        setError(errMsg);
      } finally {
        // Si aucun token n'est arrivé, on met un message d'erreur explicite
        if (!streamCompleted && accumulated === "") {
          setMessages((m) =>
            m.map((msg) =>
              msg.id === agentMsgId && msg.kind === "agent"
                ? {
                    ...msg,
                    text:
                      "Erreur : aucune réponse reçue du serveur. " +
                      "Vérifie que le backend RAG tourne et que le corpus contient des documents indexés.",
                  }
                : msg,
            ),
          );
        } else if (streamCompleted && accumulated.trim().length > 0) {
          // Persistance backend de la réponse RAG complète + sources
          if (activeId) {
            const saved = await persistMessage(
              activeId,
              "assistant",
              "agent",
              accumulated,
              {
                sources:
                  receivedSources.length > 0
                    ? (receivedSources as unknown as Record<string, unknown>[])
                    : null,
                usage: receivedUsage,
              },
            );
            reconcileAgentId(agentMsgId, saved?.id);
          }
        }
      }
    },
    [token, activeId, persistMessage, reconcileAgentId],
  );

  // ============================================================
  // Sous-fonction : recherche web live (Tavily, J41.B)
  // ============================================================

  const runWebSearchStream = useCallback(
    async (question: string) => {
      if (!token) return;

      const agentMsgId = nextId();
      let accumulated = "";
      let receivedSources: WebSource[] = [];
      let receivedUsage: MessageUsage | undefined;
      let streamCompleted = false;

      setMessages((m) => [
        ...m,
        { id: agentMsgId, kind: "agent", text: "", webSources: [] },
      ]);

      try {
        await streamWebSearchAnswer({
          question,
          token,
          maxResults: 5,
          callbacks: {
            onSources: (sources) => {
              receivedSources = sources;
              setMessages((m) =>
                m.map((msg) =>
                  msg.id === agentMsgId && msg.kind === "agent"
                    ? { ...msg, webSources: sources }
                    : msg,
                ),
              );
            },
            onToken: (tk) => {
              accumulated += tk;
              const snapshot = accumulated;
              setMessages((m) =>
                m.map((msg) =>
                  msg.id === agentMsgId && msg.kind === "agent"
                    ? { ...msg, text: snapshot }
                    : msg,
                ),
              );
            },
            onDone: (stats) => {
              streamCompleted = true;
              if (stats.total_tokens != null) {
                receivedUsage = {
                  promptTokens: stats.prompt_tokens ?? 0,
                  completionTokens: stats.completion_tokens ?? 0,
                  totalTokens: stats.total_tokens,
                  costUsd: stats.cost_usd ?? 0,
                  model: stats.model_used ?? "",
                };
                setMessages((m) =>
                  m.map((msg) =>
                    msg.id === agentMsgId && msg.kind === "agent"
                      ? { ...msg, usage: receivedUsage }
                      : msg,
                  ),
                );
              }
            },
            onError: (errMsg) => {
              setError(errMsg);
              toast.error(`Recherche web indisponible : ${errMsg}`);
              setMessages((m) =>
                m.map((msg) =>
                  msg.id === agentMsgId && msg.kind === "agent"
                    ? { ...msg, text: (msg.text || "") + `\n\n**Erreur** : ${errMsg}` }
                    : msg,
                ),
              );
            },
          },
        });
      } catch (e: unknown) {
        const errMsg = e instanceof Error ? e.message : "Erreur inconnue";
        setError(errMsg);
        toast.error(`Recherche web indisponible : ${errMsg}`);
      } finally {
        if (!streamCompleted && accumulated === "") {
          setMessages((m) =>
            m.map((msg) =>
              msg.id === agentMsgId && msg.kind === "agent"
                ? {
                    ...msg,
                    text:
                      "Erreur : aucune réponse reçue du serveur. " +
                      "Vérifie que la recherche web est bien configurée côté serveur.",
                  }
                : msg,
            ),
          );
        } else if (streamCompleted && accumulated.trim().length > 0) {
          if (activeId) {
            const saved = await persistMessage(
              activeId,
              "assistant",
              "agent",
              accumulated,
              {
                sources:
                  receivedSources.length > 0
                    ? (receivedSources as unknown as Record<string, unknown>[])
                    : null,
                usage: receivedUsage,
              },
            );
            reconcileAgentId(agentMsgId, saved?.id);
          }
        }
      }
    },
    [token, activeId, persistMessage, reconcileAgentId],
  );

  // ============================================================
  // Feedback utile / à améliorer (J30)
  // ============================================================

  // Id local temporaire (nextId()) tant que reconcileAgentId n'a pas
  // encore remplacé par le vrai UUID backend : appeler l'API avec cet
  // id échouerait en 404.
  const isLocalId = (id: string) => id.startsWith("m_");

  const updateFeedback = useCallback(
    async (messageId: string, feedback: MessageFeedback) => {
      if (!token) return;

      if (isLocalId(messageId)) {
        toast.error("Le message est en cours de sauvegarde, réessaie dans un instant.");
        return;
      }

      const target = messages.find((msg) => msg.id === messageId);
      const previousFeedback =
        target && target.kind === "agent" ? target.feedback ?? null : null;

      // Update optimiste
      setMessages((m) =>
        m.map((msg) =>
          msg.id === messageId && msg.kind === "agent"
            ? { ...msg, feedback }
            : msg,
        ),
      );

      try {
        await updateMessageFeedback(token, messageId, feedback);
        toast.success(feedback ? "Merci pour ton retour" : "Retour enregistré");
      } catch (e: unknown) {
        // Rollback
        setMessages((m) =>
          m.map((msg) =>
            msg.id === messageId && msg.kind === "agent"
              ? { ...msg, feedback: previousFeedback }
              : msg,
          ),
        );
        const detail =
          e instanceof ApiError
            ? e.detail
            : e instanceof Error
            ? e.message
            : "Erreur inconnue";
        toast.error("Impossible d'enregistrer ton retour : " + detail);
      }
    },
    [token, messages],
  );

  // ============================================================
  // Régénération d'une réponse (J30)
  // ============================================================

  const regenerateMessage = useCallback(
    async (agentMessageId: string) => {
      if (loading || !token) return;

      const idx = messages.findIndex((m) => m.id === agentMessageId);
      if (idx === -1 || messages[idx].kind !== "agent") {
        toast.error("Impossible de régénérer, conversation incomplète");
        return;
      }

      // Cherche le message user le plus proche avant ce message agent
      let userText: string | null = null;
      for (let i = idx - 1; i >= 0; i--) {
        const m = messages[i];
        if (m.kind === "user") {
          userText = m.text;
          break;
        }
      }

      if (userText === null) {
        toast.error("Impossible de régénérer, conversation incomplète");
        return;
      }

      toast.info("Nouvelle réponse en cours...");

      // Retire la bulle agent actuelle localement
      setMessages((m) => m.filter((msg) => msg.id !== agentMessageId));

      // Supprime le message backend (best-effort : la régénération continue
      // même en cas d'échec, pour ne pas bloquer l'utilisateur)
      if (!isLocalId(agentMessageId)) {
        try {
          await deleteMessage(token, agentMessageId);
        } catch (e) {
          console.error(
            "[use-agent-chat] échec suppression message pour régénération :",
            e,
          );
        }
      }

      const { documentId: activePdfId, corpusId: activeCorpusId } =
        getActiveScopedIds();

      setLoading(true);
      try {
        if (activeCorpusId) {
          await runCorpusRagStream(userText, activeCorpusId);
        } else if (activePdfId) {
          await runRagStream(userText, activePdfId);
        } else {
          await runAgentChat(userText);
        }
      } finally {
        setLoading(false);
      }
    },
    [
      token,
      loading,
      messages,
      getActiveScopedIds,
      runCorpusRagStream,
      runRagStream,
      runAgentChat,
    ],
  );

  const clearError = useCallback(() => setError(null), []);

  return {
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
  };
}