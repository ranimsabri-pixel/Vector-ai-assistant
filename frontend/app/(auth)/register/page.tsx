"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { api, ApiError } from "@/lib/api";
import { useAuthStore, type User } from "@/lib/store/auth";
import { useDiscussionsStore } from "@/lib/store/discussions";
import { createConversation } from "@/lib/conversations";

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // 1. Register
      await api<User>("/auth/register", {
        method: "POST",
        body: {
          email,
          password,
          full_name: fullName || null,
        },
      });

      // 2. Login automatique
      const { access_token } = await api<TokenResponse>("/auth/login", {
        method: "POST",
        body: { username: email, password, grant_type: "password" },
        isForm: true,
      });

      // 3. Récupérer le profil
      const user = await api<User>("/users/me", {
        method: "GET",
        token: access_token,
      });

      setAuth(access_token, user);

      // Nouvelle discussion vierge des la premiere inscription (meme logique
      // que login.tsx J41.A) — sans quoi un nouvel utilisateur atterrit avec
      // une sidebar vide et aucun activeId, donc son premier message ne
      // serait jamais persiste. Best-effort : une erreur ici ne doit jamais
      // bloquer l'inscription.
      try {
        const conv = await createConversation(access_token, {
          title: "Nouvelle discussion",
          agent_slug: "vector",
        });
        useDiscussionsStore.getState().addExistingConversation({
          id: conv.id,
          title: conv.title,
          createdAt: conv.created_at,
          updatedAt: conv.updated_at,
          documentId: conv.document_id,
          documentName: conv.document_name,
          corpusId: conv.corpus_id,
          corpusName: conv.corpus_name,
          pending: false,
          isPinned: conv.is_pinned,
        });
      } catch (convErr) {
        console.error("[register] Erreur création conversation initiale :", convErr);
      }

      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Impossible de créer le compte. Réessaie.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-md p-8 bg-card rounded-2xl border border-border shadow-xl"
    >
      <h1 className="text-2xl font-bold mb-2">Créer un compte</h1>
      <p className="text-sm text-muted-foreground mb-6">
        Rejoins Vector pour analyser tes données
      </p>

      {error && (
        <div
          data-testid="signup-error-message"
          className="mb-4 p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg"
        >
          {error}
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label htmlFor="email" className="block text-sm mb-1 text-foreground">
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            className="w-full px-3 py-2 bg-muted border border-border rounded-lg focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </div>

        <div>
          <label htmlFor="fullName" className="block text-sm mb-1 text-foreground">
            Nom complet <span className="text-muted-foreground">(optionnel)</span>
          </label>
          <input
            id="fullName"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            autoComplete="name"
            className="w-full px-3 py-2 bg-muted border border-border rounded-lg focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm mb-1 text-foreground">
            Mot de passe <span className="text-muted-foreground">(min 8 caractères)</span>
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            className="w-full px-3 py-2 bg-muted border border-border rounded-lg focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full mt-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
      >
        {loading ? "Création..." : "Créer mon compte"}
      </button>

      <p className="text-sm text-muted-foreground mt-4 text-center">
        Déjà un compte ?{" "}
        <Link href="/login" className="text-emerald-400 hover:text-emerald-300 hover:underline">
          Se connecter
        </Link>
      </p>
    </form>
  );
}