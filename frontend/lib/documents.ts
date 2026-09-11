"use client";

import { api } from "./api";

// =========================
// Types
// =========================

export type DocumentStatus =
  | "uploaded"
  | "parsing"
  | "chunking"
  | "embedding"
  | "ready"
  | "error";

export type FileType = "pdf" | "docx" | "pptx" | "txt" | "md";

export type DocumentSummary = {
  id: string;
  name: string;
  original_filename: string;
  file_type: FileType;
  status: DocumentStatus;
  chunk_count: number;
  page_count: number | null;
  created_at: string;
};

export type DocumentDetail = DocumentSummary & {
  user_id: string;
  file_size_bytes: number;
  error_message: string | null;
  doc_metadata: Record<string, unknown> | null;
  updated_at: string;
};

export type DocumentUploadResponse = {
  id: string;
  name: string;
  status: DocumentStatus;
  file_size_bytes: number;
  message: string;
};

// =========================
// Formatage par type de fichier
// =========================

export function getFileTypeLabel(fileType: string): string {
  if (fileType === "docx") return "WORD";
  if (fileType === "pptx") return "SLIDES";
  if (fileType === "txt") return "TXT";
  if (fileType === "md") return "MD";
  return "PDF";
}

export function getFileTypeColorClass(fileType: string): string {
  if (fileType === "docx") return "bg-blue-600";
  if (fileType === "pptx") return "bg-orange-600";
  if (fileType === "txt") return "bg-zinc-600";
  if (fileType === "md") return "bg-violet-600";
  return "bg-emerald-600";
}

// Deduit le type depuis le nom de fichier (cote client, avant reponse backend)
export function getFileTypeFromName(fileName: string): FileType {
  const lower = fileName.toLowerCase();
  if (lower.endsWith(".docx")) return "docx";
  if (lower.endsWith(".pptx")) return "pptx";
  if (lower.endsWith(".md")) return "md";
  if (lower.endsWith(".txt")) return "txt";
  return "pdf";
}

// =========================
// Upload
// =========================

export async function uploadDocument(
  token: string,
  file: File,
  name?: string,
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (name) formData.append("name", name);

  return api<DocumentUploadResponse>("/documents/upload", {
    method: "POST",
    token,
    body: formData,
  });
}

// =========================
// Read
// =========================

export async function fetchUserDocuments(
  token: string,
): Promise<DocumentSummary[]> {
  return api<DocumentSummary[]>("/documents", {
    method: "GET",
    token,
  });
}

export async function fetchDocument(
  token: string,
  documentId: string,
): Promise<DocumentDetail> {
  return api<DocumentDetail>(`/documents/${documentId}`, {
    method: "GET",
    token,
  });
}

// =========================
// Download (docx : pas de viewer, on telecharge directement)
// =========================

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function downloadDocument(
  token: string,
  documentId: string,
  fileName: string,
): Promise<void> {
  const response = await fetch(`${API_URL}/documents/${documentId}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`Erreur ${response.status} lors du téléchargement`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// =========================
// Reingest (S5 J36)
// =========================

export async function reingestDocument(
  token: string,
  documentId: string,
): Promise<DocumentDetail> {
  return api<DocumentDetail>(`/documents/${documentId}/reingest`, {
    method: "POST",
    token,
  });
}

// =========================
// Delete
// =========================

export async function deleteDocument(
  token: string,
  documentId: string,
): Promise<void> {
  await api<void>(`/documents/${documentId}`, {
    method: "DELETE",
    token,
  });
}

// =========================
// Polling helper
// =========================

/**
 * Attend qu'un document soit "ready" (ou "error").
 * Poll toutes les intervalMs ms, jusqu'à maxAttempts.
 */
export async function pollDocumentReady(
  documentId: string,
  token: string,
  {
    maxAttempts = 60,          // 60 essais × 2s = 2 minutes max
    intervalMs = 2000,
    onProgress,
  }: {
    maxAttempts?: number;
    intervalMs?: number;
    onProgress?: (status: DocumentStatus) => void;
  } = {},
): Promise<DocumentDetail> {
  for (let i = 0; i < maxAttempts; i++) {
    const doc = await fetchDocument(token, documentId);
    onProgress?.(doc.status);

    if (doc.status === "ready") return doc;
    if (doc.status === "error") {
      throw new Error(
        doc.error_message || "L'ingestion du document a échoué",
      );
    }

    await new Promise((r) => setTimeout(r, intervalMs));
  }

  throw new Error(
    "Timeout : le document n'a pas fini d'être ingéré en 2 minutes",
  );
}