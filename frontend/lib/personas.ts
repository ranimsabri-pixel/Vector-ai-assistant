"use client";

import { api } from "./api";
import type { DocumentSummary } from "./documents";
import type { CorpusSummary } from "./corpus";

// ============================================================
// Types — miroir des schémas Pydantic backend (app/schemas/persona.py)
// ============================================================

export type PersonaListItem = {
  id: string;
  name: string;
  description: string | null;
  icon: string;
  color: string;
  is_system: boolean;
  created_at: string;
};

export type PersonaDetail = PersonaListItem & {
  system_prompt: string;
  documents: DocumentSummary[];
  corpora: CorpusSummary[];
};

export type CreatePersonaPayload = {
  name: string;
  description?: string | null;
  system_prompt: string;
  icon: string;
  color: string;
};

export type UpdatePersonaPayload = Partial<CreatePersonaPayload>;

// Whitelist d'icônes lucide-react — doit rester synchro avec
// ALLOWED_ICONS dans app/schemas/persona.py (backend).
export const PERSONA_ICONS = [
  "Bot", "Sparkles", "Briefcase", "LineChart", "TrendingUp", "Users",
  "MessageCircle", "PieChart", "BarChart3", "Target", "Lightbulb", "Rocket",
  "Building2", "Calculator", "FileText", "Search", "Globe", "ShoppingCart",
  "DollarSign", "Megaphone", "HeartHandshake", "GraduationCap", "Scale",
  "Stethoscope", "Code", "Database", "Newspaper", "Compass", "Award", "Brain",
] as const;

// Palette de couleurs — doit rester synchro avec ALLOWED_COLORS (backend).
export const PERSONA_COLORS = [
  "#2D8659", "#3B82F6", "#8B5CF6", "#F59E0B",
  "#EF4444", "#EC4899", "#14B8A6", "#6366F1",
] as const;

// ============================================================
// CRUD Personas
// ============================================================

export async function listPersonas(token: string): Promise<PersonaListItem[]> {
  return api<PersonaListItem[]>("/personas", {
    method: "GET",
    token,
  });
}

export async function fetchPersona(
  token: string,
  personaId: string,
): Promise<PersonaDetail> {
  return api<PersonaDetail>(`/personas/${personaId}`, {
    method: "GET",
    token,
  });
}

export async function createPersona(
  token: string,
  payload: CreatePersonaPayload,
): Promise<PersonaDetail> {
  return api<PersonaDetail>("/personas", {
    method: "POST",
    token,
    body: {
      name: payload.name,
      description: payload.description ?? null,
      system_prompt: payload.system_prompt,
      icon: payload.icon,
      color: payload.color,
    },
  });
}

export async function updatePersona(
  token: string,
  personaId: string,
  payload: UpdatePersonaPayload,
): Promise<PersonaDetail> {
  return api<PersonaDetail>(`/personas/${personaId}`, {
    method: "PUT",
    token,
    body: payload,
  });
}

export async function deletePersona(
  token: string,
  personaId: string,
): Promise<void> {
  await api<void>(`/personas/${personaId}`, {
    method: "DELETE",
    token,
  });
}

// ============================================================
// Documents — link / unlink
// ============================================================

export async function linkDocumentsToPersona(
  token: string,
  personaId: string,
  documentIds: string[],
): Promise<PersonaDetail> {
  return api<PersonaDetail>(`/personas/${personaId}/documents`, {
    method: "POST",
    token,
    body: { document_ids: documentIds },
  });
}

export async function unlinkDocumentFromPersona(
  token: string,
  personaId: string,
  documentId: string,
): Promise<PersonaDetail> {
  return api<PersonaDetail>(`/personas/${personaId}/documents/${documentId}`, {
    method: "DELETE",
    token,
  });
}

// ============================================================
// Corpus — link / unlink
// ============================================================

export async function linkCorporaToPersona(
  token: string,
  personaId: string,
  corpusIds: string[],
): Promise<PersonaDetail> {
  return api<PersonaDetail>(`/personas/${personaId}/corpora`, {
    method: "POST",
    token,
    body: { corpus_ids: corpusIds },
  });
}

export async function unlinkCorpusFromPersona(
  token: string,
  personaId: string,
  corpusId: string,
): Promise<PersonaDetail> {
  return api<PersonaDetail>(`/personas/${personaId}/corpora/${corpusId}`, {
    method: "DELETE",
    token,
  });
}
