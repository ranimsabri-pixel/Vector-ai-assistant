/**
 * Client API pour l'agent Vector — tool calling.
 * Cohérent avec lib/datasets.ts : utilise le helper centralisé api().
 */
import { api } from "./api";
import type { ToolName } from "./quick_actions";

// =========================
// Types — miroir des schémas Pydantic backend
// =========================

export type ToolCallStatus = "ok" | "error";

export type ToolCallTrace = {
  name: string;
  args: Record<string, unknown>;
  result_summary: string;
  status: ToolCallStatus;
  duration_ms: number;
};

export type AgentArtifacts = {
  dashboard_id?: string;
  dataset_id?: string;
};

export type AgentChatResponse = {
  message: string;
  tool_calls: ToolCallTrace[];
  artifacts: AgentArtifacts | null;
  iterations: number;
  // NEW J41+ Feature 2 — compteur de tokens/cout
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  cost_usd: number | null;
  model_used: string | null;
};

export type AgentChatRequest = {
  message: string;
  conversation_id?: string | null;
  // NEW J41+ Feature 3 — images jointes (vision)
  attachments?: Record<string, unknown>[] | null;
};

// =========================
// Fonctions API
// =========================

/**
 * Envoie un message à l'agent Vector. L'agent peut appeler plusieurs
 * outils en interne avant de produire sa réponse finale.
 */
export async function agentChat(
  message: string,
  token: string,
  conversationId?: string | null,
  attachments?: Record<string, unknown>[] | null,
): Promise<AgentChatResponse> {
  return api<AgentChatResponse>("/agent/chat", {
    method: "POST",
    token,
    body: {
      message,
      conversation_id: conversationId ?? null,
      attachments: attachments ?? null,
    } satisfies AgentChatRequest,
  });
}
/**
 * Exécute une action rapide via le tool calling backend.
 * On construit un prompt très directif qui force le LLM à appeler l'outil voulu
 * avec les paramètres exacts du formulaire — pas de fantaisie possible.
 */
export async function agentRunTool(
  toolName: ToolName,
  params: Record<string, string | number>,
  token: string,
): Promise<AgentChatResponse> {
  // J20 : appel DIRECT à l'endpoint /agent/run-tool (sans LLM).
  // Élimine les hallucinations (UUID tronqué, lien markdown inventé)
  // et divise par 5-10 le temps de réponse pour les actions rapides.
  return api<AgentChatResponse>("/agent/run-tool", {
    method: "POST",
    token,
    body: {
      tool_name: toolName,
      arguments: params,
    },
  });
}