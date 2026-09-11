"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useAuthStore } from "@/lib/store/auth";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface UseChatOptions {
  agentSlug?: string;
}

export function useChat({ agentSlug = "vector" }: UseChatOptions = {}) {
  const token = useAuthStore((s) => s.token);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Connexion WebSocket au montage / changement de token
  useEffect(() => {
    if (!token) return;

    const url = `${WS_URL}/ws/chat?token=${encodeURIComponent(token)}&agent_slug=${agentSlug}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    ws.onerror = () => {
      setError("Erreur de connexion au chat");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "token") {
        // Append au dernier message assistant
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant") {
            return [
              ...prev.slice(0, -1),
              { ...last, content: last.content + data.content },
            ];
          }
          return prev;
        });
      } else if (data.type === "done") {
        setIsStreaming(false);
      } else if (data.type === "error") {
        setError(data.detail);
        setIsStreaming(false);
      }
    };

    return () => {
      ws.close();
    };
  }, [token, agentSlug]);

  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError("Non connecté");
      return;
    }

    setError(null);
    setIsStreaming(true);

    // Ajouter le message user + placeholder assistant vide
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content },
      { id: crypto.randomUUID(), role: "assistant", content: "" },
    ]);

    wsRef.current.send(
      JSON.stringify({
        type: "user_message",
        content,
      })
    );
  }, []);

  return {
    messages,
    isConnected,
    isStreaming,
    error,
    sendMessage,
  };
}