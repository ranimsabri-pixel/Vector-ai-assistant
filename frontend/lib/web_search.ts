"use client";

// =========================
// Types
// =========================

export type WebSource = {
  title: string;
  url: string;
  snippet: string;
};

export type WebSearchDoneStats = {
  tokens_streamed: number;
  sources_count: number;
  // NEW J41+ Feature 2 — usage reel (absent si l'API n'a pas renvoye l'usage)
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  cost_usd?: number;
  model_used?: string;
};

export type WebSearchStreamCallbacks = {
  onSources?: (sources: WebSource[]) => void;
  onToken?: (token: string) => void;
  onDone?: (stats: WebSearchDoneStats) => void;
  onError?: (message: string) => void;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// =========================
// Streaming SSE natif — meme logique de parsing que lib/rag.ts, mais
// evenement "web_sources" (pas "sources") et type WebSource distinct.
// =========================

export async function streamWebSearchAnswer({
  question,
  token,
  maxResults = 5,
  callbacks,
}: {
  question: string;
  token: string;
  maxResults?: number;
  callbacks: WebSearchStreamCallbacks;
}): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/agent/chat-web`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ question, max_results: maxResults }),
    });

    if (!response.ok) {
      const errText = await response.text();
      callbacks.onError?.(`Erreur ${response.status} : ${errText.slice(0, 300)}`);
      return;
    }

    if (!response.body) {
      callbacks.onError?.("Pas de body dans la réponse SSE");
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    let currentEvent: string | null = null;
    let currentData: string[] = [];

    const flushEvent = () => {
      if (currentEvent && currentData.length > 0) {
        dispatchEvent(currentEvent, currentData.join("\n"), callbacks);
      }
      currentEvent = null;
      currentData = [];
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        flushEvent();
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      let newlineIdx: number;
      while ((newlineIdx = buffer.indexOf("\n")) !== -1) {
        let line = buffer.slice(0, newlineIdx);
        buffer = buffer.slice(newlineIdx + 1);
        if (line.endsWith("\r")) line = line.slice(0, -1);

        if (line === "") {
          flushEvent();
        } else if (line.startsWith("event:")) {
          if (currentEvent !== null) flushEvent();
          currentEvent = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          const dataContent = line.startsWith("data: ") ? line.slice(6) : line.slice(5);
          currentData.push(dataContent);
        }
      }
    }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Erreur inconnue";
    callbacks.onError?.(msg);
  }
}

function dispatchEvent(
  eventType: string,
  dataStr: string,
  callbacks: WebSearchStreamCallbacks,
): void {
  try {
    switch (eventType) {
      case "web_sources": {
        const parsed = JSON.parse(dataStr) as WebSource[];
        callbacks.onSources?.(parsed || []);
        break;
      }
      case "token": {
        let tokenText: string;
        try {
          const parsed = JSON.parse(dataStr);
          tokenText = typeof parsed === "string" ? parsed : dataStr;
        } catch {
          tokenText = dataStr;
        }
        callbacks.onToken?.(tokenText);
        break;
      }
      case "done": {
        const stats = JSON.parse(dataStr) as WebSearchDoneStats;
        callbacks.onDone?.(stats);
        break;
      }
      case "error": {
        callbacks.onError?.(dataStr);
        break;
      }
    }
  } catch (e) {
    console.warn("[web_search SSE dispatch error]", eventType, dataStr.slice(0, 100), e);
  }
}
