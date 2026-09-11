"use client";

import { api } from "./api";
import type { MessageResponse } from "./conversations";

export type MessageFeedback = "positive" | "negative" | null;

export async function updateMessageFeedback(
  token: string,
  messageId: string,
  feedback: MessageFeedback,
): Promise<MessageResponse> {
  return api<MessageResponse>(`/messages/${messageId}/feedback`, {
    method: "PATCH",
    token,
    body: { feedback },
  });
}

export async function deleteMessage(
  token: string,
  messageId: string,
): Promise<void> {
  return api<void>(`/messages/${messageId}`, {
    method: "DELETE",
    token,
  });
}
