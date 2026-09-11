"use client";

import { api } from "./api";

// ============================================================
// Types
// ============================================================

export type MessageResponse = {
  id: string;
  conversation_id: string;
  role: string;
  message_kind: string;
  content: string;
  tool_calls: unknown[] | null;
  sources: unknown[] | null;
  extra_data: Record<string, unknown> | null;
  feedback: "positive" | "negative" | null;
  created_at: string;
  // NEW J41+ Feature 2 — compteur de tokens/cout
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  cost_usd: number | null;
  model_used: string | null;
  // NEW J41+ Feature 3 — pieces jointes (images)
  attachments: Record<string, unknown>[] | null;
};

// NEW J41+ Feature 2 — stats agregees d'une conversation
export type ConversationStats = {
  total_messages: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_response_tokens: number;
};

export type ConversationSummary = {
  id: string;
  title: string;
  is_pinned: boolean;  // NEW J27
  document_id: string | null;
  document_name: string | null;
  corpus_id: string | null;  // NEW J34
  corpus_name: string | null;  // NEW J34
  persona_id: string | null;  // NEW J49
  persona_name: string | null;  // NEW J49
  persona_icon: string | null;  // NEW J49
  persona_color: string | null;  // NEW J49
  message_count: number;
  created_at: string;
  updated_at: string;
};

export type ConversationDetail = {
  id: string;
  title: string;
  is_pinned: boolean;  // NEW J27
  document_id: string | null;
  document_name: string | null;
  corpus_id: string | null;  // NEW J34
  corpus_name: string | null;  // NEW J34
  persona_id: string | null;  // NEW J49
  persona_name: string | null;  // NEW J49
  persona_icon: string | null;  // NEW J49
  persona_color: string | null;  // NEW J49
  agent_id: string;
  created_at: string;
  updated_at: string;
  messages: MessageResponse[];
};

export type CreateConversationPayload = {
  title?: string;
  document_id?: string | null;
  corpus_id?: string | null;  // NEW J34
  persona_id?: string | null;  // NEW J49
  agent_slug?: string;
};

export type CreateMessagePayload = {
  role: string;              // "user" | "assistant" | "system"
  message_kind: string;      // "user" | "agent" | "status" | "tool" | "pdf_attachment" | "form"
  content: string;
  tool_calls?: unknown[] | null;
  sources?: unknown[] | null;
  extra_data?: Record<string, unknown> | null;
  // NEW J41+ Feature 2 — compteur de tokens/cout
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  cost_usd?: number | null;
  model_used?: string | null;
  // NEW J41+ Feature 3 — pieces jointes (images)
  attachments?: Record<string, unknown>[] | null;
};

// ============================================================
// CRUD Conversations
// ============================================================

export async function listConversations(
  token: string,
  limit = 50,
): Promise<ConversationSummary[]> {
  return api<ConversationSummary[]>(`/conversations?limit=${limit}`, {
    method: "GET",
    token,
  });
}

export async function getConversation(
  token: string,
  conversationId: string,
): Promise<ConversationDetail> {
  return api<ConversationDetail>(`/conversations/${conversationId}`, {
    method: "GET",
    token,
  });
}

export async function createConversation(
  token: string,
  payload: CreateConversationPayload = {},
): Promise<ConversationDetail> {
  return api<ConversationDetail>(`/conversations`, {
    method: "POST",
    token,
    body: {
      title: payload.title,
      document_id: payload.document_id ?? null,
      corpus_id: payload.corpus_id ?? null,
      persona_id: payload.persona_id ?? null,
      agent_slug: payload.agent_slug ?? "vector",
    },
  });
}

export async function renameConversation(
  token: string,
  conversationId: string,
  newTitle: string,
): Promise<ConversationDetail> {
  return api<ConversationDetail>(`/conversations/${conversationId}`, {
    method: "PATCH",
    token,
    body: { title: newTitle },
  });
}
export async function generateConversationTitle(
  token: string,
  conversationId: string,
): Promise<ConversationSummary> {
  return api<ConversationSummary>(
    `/conversations/${conversationId}/generate-title`,
    { method: "POST", token },
  );
}

export async function togglePinConversation(
  token: string,
  conversationId: string,
  isPinned: boolean,
): Promise<ConversationDetail> {
  return api<ConversationDetail>(`/conversations/${conversationId}`, {
    method: "PATCH",
    token,
    body: { is_pinned: isPinned },
  });
}
// NEW J49 — verrouille cote backend des que la conversation a des messages
// (409 si deja des messages). Utilise par le PersonaSelector.
export async function setConversationPersona(
  token: string,
  conversationId: string,
  personaId: string,
): Promise<ConversationDetail> {
  return api<ConversationDetail>(`/conversations/${conversationId}`, {
    method: "PATCH",
    token,
    body: { persona_id: personaId },
  });
}

export async function deleteConversationRemote(
  token: string,
  conversationId: string,
): Promise<void> {
  await api<void>(`/conversations/${conversationId}`, {
    method: "DELETE",
    token,
  });
}

// ============================================================
// Messages — append
// ============================================================

export async function appendMessage(
  token: string,
  conversationId: string,
  payload: CreateMessagePayload,
): Promise<MessageResponse> {
  return api<MessageResponse>(
    `/conversations/${conversationId}/messages`,
    {
      method: "POST",
      token,
      body: {
        role: payload.role,
        message_kind: payload.message_kind,
        content: payload.content,
        tool_calls: payload.tool_calls ?? null,
        sources: payload.sources ?? null,
        extra_data: payload.extra_data ?? null,
        prompt_tokens: payload.prompt_tokens ?? null,
        completion_tokens: payload.completion_tokens ?? null,
        total_tokens: payload.total_tokens ?? null,
        cost_usd: payload.cost_usd ?? null,
        model_used: payload.model_used ?? null,
        attachments: payload.attachments ?? null,
      },
    },
  );
}

// ============================================================
// Stats tokens/cout (NEW J41+ Feature 2)
// ============================================================

export async function getConversationStats(
  token: string,
  conversationId: string,
): Promise<ConversationStats> {
  return api<ConversationStats>(`/conversations/${conversationId}/stats`, {
    method: "GET",
    token,
  });
}