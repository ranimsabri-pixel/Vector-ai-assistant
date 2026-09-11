"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import {
  createConversation,
  deleteConversationRemote,
  listConversations,
  renameConversation,
  setConversationPersona,
  togglePinConversation,
} from "@/lib/conversations";

// ============================================================
// Types
// ============================================================

export interface Discussion {
  id: string;              // UUID backend (ou tempId pendant création optimiste)
  title: string;
  createdAt: string;
  updatedAt?: string;      // NEW J27 — pour tri par période
  documentId?: string | null;
  documentName?: string | null;
  corpusId?: string | null;    // NEW J34
  corpusName?: string | null;  // NEW J34
  personaId?: string | null;    // NEW J49 — null = persona système Vector
  personaName?: string | null;  // NEW J49
  personaIcon?: string | null;  // NEW J49
  personaColor?: string | null; // NEW J49
  pending?: boolean;       // true = en cours de création côté backend
  isPinned?: boolean;      // NEW J27 — conversation épinglée
}

interface DiscussionsState {
  discussions: Discussion[];
  activeId: string | null;
  searchQuery: string;     // NEW J27

  // API publique (garde la même signature qu'avant pour ne pas casser AgentPanel)
  addDiscussion: () => string;
  deleteDiscussion: (id: string) => void;
  setActive: (id: string | null) => void;
  renameDiscussion: (id: string, title: string) => void;
  updateDiscussionTitle: (id: string, title: string) => void;

  // Sync backend
  loadFromBackend: (token: string) => Promise<void>;
  addExistingConversation: (conv: Discussion) => void;
  addDiscussionWithDoc: (
    token: string,
    documentId: string,
    documentName: string,
  ) => Promise<string>;
  addDiscussionWithCorpus: (
    token: string,
    corpusId: string,
    corpusName: string,
  ) => Promise<string>;
  bumpUpdatedAt: (id: string) => void;
  setToken: (token: string | null) => void;

  // NEW J49 — Personas
  setPersona: (
    token: string,
    id: string,
    persona: { id: string; name: string; icon: string; color: string },
  ) => Promise<void>;

  // NEW J27
  togglePin: (id: string) => void;
  setSearchQuery: (query: string) => void;
}

// ============================================================
// Store
// ============================================================

// Variable interne — le token courant (mis à jour par setToken depuis le hook)
let _token: string | null = null;

export const useDiscussionsStore = create<DiscussionsState>()(
  persist(
    (set, get) => ({
      discussions: [],
      activeId: null,
      searchQuery: "",

      // ============================================================
      // API PUBLIQUE (signatures inchangées)
      // ============================================================

      addDiscussion: () => {
        // 1. Optimistic UI : bulle immédiate avec tempId
        const tempId = `temp_${Date.now()}_${Math.random().toString(36).slice(2)}`;
        const now = new Date().toISOString();
        const newDiscussion: Discussion = {
          id: tempId,
          title: "Nouvelle discussion",
          createdAt: now,
          updatedAt: now,
          pending: true,
          isPinned: false,
        };
        set((state) => ({
          discussions: [newDiscussion, ...state.discussions],
          activeId: tempId,
        }));

        // 2. Appel backend en arrière-plan (fire-and-forget)
        if (_token) {
          createConversation(_token, {
            title: "Nouvelle discussion",
            agent_slug: "vector",
          })
            .then((conv) => {
              // 3. Remplace le tempId par le vrai UUID
              set((state) => ({
                discussions: state.discussions.map((d) =>
                  d.id === tempId
                    ? {
                        id: conv.id,
                        title: conv.title,
                        createdAt: conv.created_at,
                        updatedAt: conv.updated_at,
                        documentId: conv.document_id,
                        documentName: conv.document_name,
                        personaId: conv.persona_id,
                        personaName: conv.persona_name,
                        personaIcon: conv.persona_icon,
                        personaColor: conv.persona_color,
                        pending: false,
                        isPinned: conv.is_pinned,
                      }
                    : d,
                ),
                activeId: state.activeId === tempId ? conv.id : state.activeId,
              }));
            })
            .catch((err) => {
              console.error("[discussions] Erreur création backend :", err);
              // Rollback : retire la conv temporaire
              set((state) => ({
                discussions: state.discussions.filter((d) => d.id !== tempId),
                activeId: state.activeId === tempId ? null : state.activeId,
              }));
            });
        }

        return tempId;
      },

      deleteDiscussion: (id) => {
        // 1. UI optimiste : retire tout de suite
        const snapshot = get().discussions;
        set((state) => ({
          discussions: state.discussions.filter((d) => d.id !== id),
          activeId: state.activeId === id ? null : state.activeId,
        }));

        // 2. Backend delete (skip si c'est un tempId : pas encore en BDD)
        if (_token && !id.startsWith("temp_")) {
          deleteConversationRemote(_token, id).catch((err) => {
            console.error("[discussions] Erreur delete backend :", err);
            // Rollback si erreur
            set({ discussions: snapshot });
          });
        }
      },

      setActive: (id) => set({ activeId: id }),

      renameDiscussion: (id, title) => {
        // 1. UI optimiste
        set((state) => ({
          discussions: state.discussions.map((d) =>
            d.id === id ? { ...d, title } : d,
          ),
        }));

        // 2. Backend rename (skip si tempId)
        if (_token && !id.startsWith("temp_")) {
          renameConversation(_token, id, title).catch((err) => {
            console.error("[discussions] Erreur rename backend :", err);
          });
        }
      },

      // NEW J41+ (feature 1) — met a jour uniquement le titre local, sans
      // appel backend (le titre a deja ete genere/persiste cote serveur par
      // generate-title ; contrairement a renameDiscussion qui, elle, appelle
      // le backend pour un renommage manuel).
      updateDiscussionTitle: (id, title) => {
        set((state) => ({
          discussions: state.discussions.map((d) =>
            d.id === id ? { ...d, title } : d,
          ),
        }));
      },

      // ============================================================
      // NOUVEAUX (J25.B)
      // ============================================================

      loadFromBackend: async (token) => {
        try {
          const remote = await listConversations(token, 50);
          set({
            discussions: remote.map((c) => ({
              id: c.id,
              title: c.title,
              createdAt: c.created_at,
              updatedAt: c.updated_at,       // NEW J27
              documentId: c.document_id,
              documentName: c.document_name,
              corpusId: c.corpus_id,          // NEW J34
              corpusName: c.corpus_name,      // NEW J34
              personaId: c.persona_id,        // NEW J49
              personaName: c.persona_name,    // NEW J49
              personaIcon: c.persona_icon,    // NEW J49
              personaColor: c.persona_color,  // NEW J49
              pending: false,
              isPinned: c.is_pinned,          // NEW J27
            })),
          });
        } catch (err) {
          console.error("[discussions] loadFromBackend erreur :", err);
        }
      },

      // NEW J41.A — insere une conversation deja creee cote backend (login
      // effectif) et la rend active. Pas d'appel reseau ici : le POST
      // /conversations a deja ete fait par l'appelant avec un token frais,
      // avant meme que ce store connaisse un _token valide.
      addExistingConversation: (conv) => {
        set((state) => ({
          discussions: [conv, ...state.discussions.filter((d) => d.id !== conv.id)],
          activeId: conv.id,
        }));
      },

      addDiscussionWithDoc: async (token, documentId, documentName) => {
        // Crée immédiatement une conv liée à un PDF (utilisé quand on attache un PDF)
        const tempId = `temp_${Date.now()}_${Math.random().toString(36).slice(2)}`;
        const now = new Date().toISOString();
        set((state) => ({
          discussions: [
            {
              id: tempId,
              title: documentName.replace(/\.pdf$/i, ""),
              createdAt: now,
              updatedAt: now,
              documentId,
              documentName,
              pending: true,
              isPinned: false,
            },
            ...state.discussions,
          ],
          activeId: tempId,
        }));

        try {
          const conv = await createConversation(token, {
            document_id: documentId,
            agent_slug: "vector",
          });
          set((state) => ({
            discussions: state.discussions.map((d) =>
              d.id === tempId
                ? {
                    id: conv.id,
                    title: conv.title,
                    createdAt: conv.created_at,
                    updatedAt: conv.updated_at,
                    documentId: conv.document_id,
                    documentName: conv.document_name,
                    corpusId: conv.corpus_id,
                    corpusName: conv.corpus_name,
                    personaId: conv.persona_id,
                    personaName: conv.persona_name,
                    personaIcon: conv.persona_icon,
                    personaColor: conv.persona_color,
                    pending: false,
                    isPinned: conv.is_pinned,
                  }
                : d,
            ),
            activeId: state.activeId === tempId ? conv.id : state.activeId,
          }));
          return conv.id;
        } catch (err) {
          console.error("[discussions] addDiscussionWithDoc erreur :", err);
          set((state) => ({
            discussions: state.discussions.filter((d) => d.id !== tempId),
            activeId: state.activeId === tempId ? null : state.activeId,
          }));
          throw err;
        }
      },

      // NEW J34 — cree une conversation liee a un corpus (RAG multi-docs)
      addDiscussionWithCorpus: async (token, corpusId, corpusName) => {
        const tempId = `temp_${Date.now()}_${Math.random().toString(36).slice(2)}`;
        const now = new Date().toISOString();
        set((state) => ({
          discussions: [
            {
              id: tempId,
              title: corpusName,
              createdAt: now,
              updatedAt: now,
              corpusId,
              corpusName,
              pending: true,
              isPinned: false,
            },
            ...state.discussions,
          ],
          activeId: tempId,
        }));

        try {
          const conv = await createConversation(token, {
            corpus_id: corpusId,
            agent_slug: "vector",
          });
          set((state) => ({
            discussions: state.discussions.map((d) =>
              d.id === tempId
                ? {
                    id: conv.id,
                    title: conv.title,
                    createdAt: conv.created_at,
                    updatedAt: conv.updated_at,
                    documentId: conv.document_id,
                    documentName: conv.document_name,
                    corpusId: conv.corpus_id,
                    corpusName: conv.corpus_name,
                    personaId: conv.persona_id,
                    personaName: conv.persona_name,
                    personaIcon: conv.persona_icon,
                    personaColor: conv.persona_color,
                    pending: false,
                    isPinned: conv.is_pinned,
                  }
                : d,
            ),
            activeId: state.activeId === tempId ? conv.id : state.activeId,
          }));
          return conv.id;
        } catch (err) {
          console.error("[discussions] addDiscussionWithCorpus erreur :", err);
          set((state) => ({
            discussions: state.discussions.filter((d) => d.id !== tempId),
            activeId: state.activeId === tempId ? null : state.activeId,
          }));
          throw err;
        }
      },

      bumpUpdatedAt: (id) => {
        // Remonte cette conversation en haut de la liste + met à jour updatedAt local
        set((state) => {
          const conv = state.discussions.find((d) => d.id === id);
          if (!conv) return state;
          const bumped = { ...conv, updatedAt: new Date().toISOString() };
          const rest = state.discussions.filter((d) => d.id !== id);
          return {
            discussions: [bumped, ...rest],
          };
        });
      },

      setToken: (token) => {
        _token = token;
      },

      // NEW J49 — change le persona d'une conversation VIDE (verrouille
      // cote backend des le 1er message, voir set_persona() service).
      setPersona: async (token, id, persona) => {
        const snapshot = get().discussions;
        set((state) => ({
          discussions: state.discussions.map((d) =>
            d.id === id
              ? {
                  ...d,
                  personaId: persona.id,
                  personaName: persona.name,
                  personaIcon: persona.icon,
                  personaColor: persona.color,
                }
              : d,
          ),
        }));

        try {
          await setConversationPersona(token, id, persona.id);
        } catch (err) {
          console.error("[discussions] setPersona erreur :", err);
          set({ discussions: snapshot });
          throw err;
        }
      },

      // ============================================================
      // NOUVEAUX (J27) — épinglage + recherche
      // ============================================================

      togglePin: (id) => {
        // 1. UI optimiste : inverser localement
        const current = get().discussions.find((d) => d.id === id);
        if (!current) return;
        const newPinned = !current.isPinned;

        set((state) => ({
          discussions: state.discussions.map((d) =>
            d.id === id ? { ...d, isPinned: newPinned } : d,
          ),
        }));

        // 2. Backend (skip si tempId — pas encore en BDD)
        if (_token && !id.startsWith("temp_")) {
          togglePinConversation(_token, id, newPinned).catch((err) => {
            console.error("[discussions] togglePin erreur :", err);
            // Rollback en cas d'erreur
            set((state) => ({
              discussions: state.discussions.map((d) =>
                d.id === id ? { ...d, isPinned: !newPinned } : d,
              ),
            }));
          });
        }
      },

      setSearchQuery: (query) => set({ searchQuery: query }),
    }),
    {
      name: "vector-discussions",
      // On persiste juste l'activeId — la liste vient toujours du backend
      // (sinon on aurait des UUID temp bloqués en localStorage après un refresh)
      partialize: (state) => ({
        activeId: state.activeId,
      }),
    },
  ),
);