"use client";

import { api } from "./api";

// ============================================================
// Types
// ============================================================

export type ShareResponse = {
  share_token: string;
  share_url: string;
  include_attachments: boolean;
};

export type PublicRagSource = {
  document_name: string | null;
  page_number: number | null;
  content_preview: string | null;
};

// NEW J49 — miniature ≤512px deja calculee (jamais l'original pleine
// resolution, qui n'est expose au frontend nulle part, meme pour le
// proprietaire authentifie).
export type PublicAttachment = {
  type: "image";
  file_name: string;
  mime_type: string;
  preview_base64: string;
};

export type PublicMessage = {
  role: string;
  message_kind: string;
  content: string;
  sources: PublicRagSource[] | null;
  attachments: PublicAttachment[] | null;
  has_hidden_attachments: boolean;
  created_at: string;
};

export type PublicConversationShare = {
  title: string;
  shared_by: string;
  messages: PublicMessage[];
};

// ============================================================
// Endpoints authentifiés (propriétaire de la conversation)
// ============================================================

export async function createShare(
  token: string,
  conversationId: string,
  includeAttachments: boolean = false,
): Promise<ShareResponse> {
  return api<ShareResponse>(`/conversations/${conversationId}/share`, {
    method: "POST",
    token,
    body: { include_attachments: includeAttachments },
  });
}

export async function revokeShare(
  token: string,
  conversationId: string,
): Promise<void> {
  await api<void>(`/conversations/${conversationId}/share`, {
    method: "DELETE",
    token,
  });
}

// ============================================================
// Endpoint public (aucun token) — appelé depuis app/share/[token]/page.tsx
// ============================================================

export async function getPublicShare(
  shareToken: string,
): Promise<PublicConversationShare> {
  return api<PublicConversationShare>(`/share/${shareToken}`);
}
