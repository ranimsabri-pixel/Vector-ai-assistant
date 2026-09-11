"use client";

import { api } from "./api";
import { streamSSE, type RagStreamCallbacks } from "./rag";
import type { DocumentSummary } from "./documents";

// ============================================================
// Types
// ============================================================

export type CorpusSummary = {
  id: string;
  name: string;
  description: string | null;
  document_count: number;
  created_at: string;
  updated_at: string;
};

export type CorpusDetail = CorpusSummary & {
  documents: DocumentSummary[];
};

export type CreateCorpusPayload = {
  name: string;
  description?: string | null;
};

export type UpdateCorpusPayload = {
  name?: string;
  description?: string | null;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ============================================================
// CRUD Corpus
// ============================================================

export async function createCorpus(
  token: string,
  payload: CreateCorpusPayload,
): Promise<CorpusDetail> {
  return api<CorpusDetail>("/corpora", {
    method: "POST",
    token,
    body: {
      name: payload.name,
      description: payload.description ?? null,
    },
  });
}

export async function listCorpora(token: string): Promise<CorpusSummary[]> {
  return api<CorpusSummary[]>("/corpora", {
    method: "GET",
    token,
  });
}

export async function fetchCorpus(
  token: string,
  corpusId: string,
): Promise<CorpusDetail> {
  return api<CorpusDetail>(`/corpora/${corpusId}`, {
    method: "GET",
    token,
  });
}

export async function updateCorpus(
  token: string,
  corpusId: string,
  payload: UpdateCorpusPayload,
): Promise<CorpusDetail> {
  return api<CorpusDetail>(`/corpora/${corpusId}`, {
    method: "PATCH",
    token,
    body: payload,
  });
}

export async function deleteCorpus(
  token: string,
  corpusId: string,
): Promise<void> {
  await api<void>(`/corpora/${corpusId}`, {
    method: "DELETE",
    token,
  });
}

// ============================================================
// Documents — add / remove
// ============================================================

export async function addDocumentsToCorpus(
  token: string,
  corpusId: string,
  documentIds: string[],
): Promise<CorpusDetail> {
  return api<CorpusDetail>(`/corpora/${corpusId}/documents`, {
    method: "POST",
    token,
    body: { document_ids: documentIds },
  });
}

export async function removeDocumentsFromCorpus(
  token: string,
  corpusId: string,
  documentIds: string[],
): Promise<CorpusDetail> {
  return api<CorpusDetail>(`/corpora/${corpusId}/documents`, {
    method: "DELETE",
    token,
    body: { document_ids: documentIds },
  });
}

// ============================================================
// Upload multi-fichiers direct (S5 J51)
// ============================================================

export type CorpusUploadedFile = {
  document_id: string;
  filename: string;
  status: string;
};

export type CorpusUploadErrorItem = {
  filename: string;
  error: string;
};

export type CorpusUploadResponse = {
  uploaded: CorpusUploadedFile[];
  errors: CorpusUploadErrorItem[];
};

export async function uploadDocumentsToCorpus(
  token: string,
  corpusId: string,
  files: File[],
): Promise<CorpusUploadResponse> {
  const formData = new FormData();
  for (const file of files) formData.append("files", file);

  return api<CorpusUploadResponse>(`/corpora/${corpusId}/documents/upload`, {
    method: "POST",
    token,
    body: formData,
  });
}

// ============================================================
// RAG streaming sur un corpus (S5 J34)
// ============================================================

export async function streamCorpusRagAnswer({
  corpusId,
  question,
  token,
  topK = 8,
  callbacks,
}: {
  corpusId: string;
  question: string;
  token: string;
  topK?: number;
  callbacks: RagStreamCallbacks;
}): Promise<void> {
  return streamSSE(
    `${API_BASE_URL}/rag/corpus-query`,
    { corpus_id: corpusId, question, top_k: topK },
    token,
    callbacks,
  );
}
