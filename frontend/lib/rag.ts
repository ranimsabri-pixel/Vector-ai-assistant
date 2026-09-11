"use client";

// =========================
// Types
// =========================

export type RagSource = {
  chunk_id: string;
  document_id: string;
  document_name?: string | null;  // NEW J34 : rempli pour les reponses corpus
  document_file_type?: "pdf" | "docx" | "pptx" | "txt" | "md";
  page_number: number | null;
  content_preview: string;
  similarity: number;
};

export type RagDoneStats = {
  chunks_retrieved: number;
  tokens_streamed: number;
  // NEW J41+ Feature 2 — usage reel (absent si l'API n'a pas renvoye l'usage)
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  cost_usd?: number;
  model_used?: string;
};

export type RagStreamCallbacks = {
  onSources?: (sources: RagSource[]) => void;
  onToken?: (token: string) => void;
  onDone?: (stats: RagDoneStats) => void;
  onError?: (message: string) => void;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// =========================
// Streaming SSE natif (fetch + ReadableStream + parser ligne-par-ligne)
// =========================

export async function streamRagAnswer({
  question,
  documentId,
  token,
  topK = 5,
  callbacks,
}: {
  question: string;
  documentId: string;
  token: string;
  topK?: number;
  callbacks: RagStreamCallbacks;
}): Promise<void> {
  const url = documentId
    ? `${API_BASE_URL}/rag/ask/${documentId}`
    : `${API_BASE_URL}/rag/ask`;

  return streamSSE(url, { question, top_k: topK }, token, callbacks);
}

/**
 * Helper generique de streaming SSE, reutilise par streamRagAnswer (par
 * document) et streamCorpusRagAnswer (lib/corpus.ts, par corpus J34).
 * Le format d'evenements backend (sources/token/done/error) est identique
 * dans les deux cas.
 */
export async function streamSSE(
  url: string,
  body: Record<string, unknown>,
  token: string,
  callbacks: RagStreamCallbacks,
): Promise<void> {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errText = await response.text();
      callbacks.onError?.(
        `Erreur ${response.status} : ${errText.slice(0, 300)}`,
      );
      return;
    }

    if (!response.body) {
      callbacks.onError?.("Pas de body dans la réponse SSE");
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    // État courant de l'événement en cours de lecture
    let currentEvent: string | null = null;
    let currentData: string[] = [];

    /** Dispatche l'événement complet quand on rencontre une ligne vide */
    const flushEvent = () => {
      if (currentEvent && currentData.length > 0) {
        const dataStr = currentData.join("\n");
        dispatchSseEvent(currentEvent, dataStr, callbacks);
      }
      currentEvent = null;
      currentData = [];
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        // Flush final si un événement était en cours
        flushEvent();
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // Parse ligne par ligne
      // (SSE utilise \n comme séparateur de lignes, \n\n comme fin d'événement.
      // Le serveur (sse-starlette) termine en fait ses lignes par \r\n : sans
      // retirer ce \r residuel, il reste colle a la fin de CHAQUE token, et le
      // navigateur le rend comme un espace lors de l'affichage -> mots coupes
      // au milieu, y compris a l'interieur du markdown genere par le LLM.)
      let newlineIdx: number;
      while ((newlineIdx = buffer.indexOf("\n")) !== -1) {
        let line = buffer.slice(0, newlineIdx);
        buffer = buffer.slice(newlineIdx + 1);
        if (line.endsWith("\r")) {
          line = line.slice(0, -1);
        }

        if (line === "") {
          // Ligne vide → fin de l'événement courant
          flushEvent();
        } else if (line.startsWith("event:")) {
          if (currentEvent !== null) {
            flushEvent();
          }
          currentEvent = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          const dataContent = line.startsWith("data: ")
            ? line.slice(6)
            : line.slice(5);
          currentData.push(dataContent);
        }
        // Autres champs SSE (id:, retry:) ignorés pour l'instant
      }
    }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Erreur inconnue";
    callbacks.onError?.(msg);
  }
}

// =========================
// Dispatch d'un événement SSE parsé
// =========================

function dispatchSseEvent(
  eventType: string,
  dataStr: string,
  callbacks: RagStreamCallbacks,
): void {
  try {
    switch (eventType) {
      case "sources": {
        const parsed = JSON.parse(dataStr) as { chunks: RagSource[] };
        callbacks.onSources?.(parsed.chunks || []);
        break;
      }
      case "token": {
        // Le token peut être encodé en JSON string OU brut selon le backend
        let tokenText: string;
        try {
          const parsed = JSON.parse(dataStr);
          tokenText = typeof parsed === "string" ? parsed : dataStr;
        } catch {
          // Pas du JSON valide → on utilise la string brute
          tokenText = dataStr;
        }
        callbacks.onToken?.(tokenText);
        break;
      }
      case "done": {
        const stats = JSON.parse(dataStr) as RagDoneStats;
        callbacks.onDone?.(stats);
        break;
      }
      case "error": {
        callbacks.onError?.(dataStr);
        break;
      }
    }
  } catch (e) {
    // On log mais on ne plante pas — les tokens peuvent avoir des caractères
    // qui cassent JSON.parse (notamment les guillemets simples)
    console.warn("[SSE dispatch error]", eventType, dataStr.slice(0, 100), e);
  }
}