"use client";

import { useEffect, useState } from "react";
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

// S5 J55 — démo publique Render. NEXT_PUBLIC_* est inline au build (export
// statique) : changer ces valeurs nécessite un rebuild, pas juste un
// redéploiement de conteneur. Doit rester cohérent avec
// DEMO_ACCOUNT_EMAIL/PASSWORD côté backend (backend/.env.example).
const DEMO_BANNER_ENABLED = process.env.NEXT_PUBLIC_DEMO_BANNER === "true";
const DEMO_EMAIL = process.env.NEXT_PUBLIC_DEMO_EMAIL ?? "";
const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD ?? "";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [accountDeleted, setAccountDeleted] = useState(false);

  useEffect(() => {
    // sessionStorage plutot que le query param "?deleted=1" seul : la
    // redirection post-suppression peut passer par un hard-redirect
    // generique (lib/api.ts) qui ne connait pas ce query param. Verifie
    // aussi l'URL pour compat descendante.
    const flagged =
      sessionStorage.getItem("vector-account-deleted") === "1" ||
      new URLSearchParams(window.location.search).get("deleted") === "1";
    if (flagged) {
      setAccountDeleted(true);
      sessionStorage.removeItem("vector-account-deleted");
    }
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // 1. Login → récupérer le token
      const { access_token } = await api<TokenResponse>("/auth/login", {
        method: "POST",
        body: { username: email, password, grant_type: "password" },
        isForm: true,
      });

      // 2. Récupérer le profil avec le token
      const user = await api<User>("/users/me", {
        method: "GET",
        token: access_token,
      });

      // 3. Stocker dans le store
      setAuth(access_token, user);

      // 4. Nouvelle discussion vierge a chaque connexion effective (J41.A) —
      // best-effort : une erreur ici ne doit jamais bloquer la connexion.
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
        console.error("[login] Erreur création conversation initiale :", convErr);
      }

      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Impossible de se connecter. Réessaie.");
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
      <h1 className="text-2xl font-bold mb-2">Connexion</h1>
      <p className="text-sm text-muted-foreground mb-6">
        Connecte-toi à ton compte Vector
      </p>

      {DEMO_BANNER_ENABLED && DEMO_EMAIL && DEMO_PASSWORD && (
        <div
          data-testid="demo-banner"
          className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-sm"
        >
          <p className="text-foreground font-medium mb-1">Compte de démonstration</p>
          <p className="text-muted-foreground mb-2">
            <span className="font-mono">{DEMO_EMAIL}</span> ·{" "}
            <span className="font-mono">{DEMO_PASSWORD}</span>
          </p>
          <button
            type="button"
            onClick={() => {
              setEmail(DEMO_EMAIL);
              setPassword(DEMO_PASSWORD);
            }}
            className="text-emerald-400 hover:text-emerald-300 hover:underline font-medium"
          >
            Remplir automatiquement
          </button>
        </div>
      )}

      {accountDeleted && (
        <div
          data-testid="account-deleted-message"
          className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/30 text-emerald-500 text-sm rounded-lg"
        >
          Ton compte a bien été supprimé définitivement.
        </div>
      )}

      {error && (
        <div
          data-testid="login-error-message"
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
          <label htmlFor="password" className="block text-sm mb-1 text-foreground">
            Mot de passe
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="current-password"
            className="w-full px-3 py-2 bg-muted border border-border rounded-lg focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full mt-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
      >
        {loading ? "Connexion..." : "Se connecter"}
      </button>

      <p className="text-sm text-muted-foreground mt-4 text-center">
        Pas de compte ?{" "}
        <Link href="/register" className="text-emerald-400 hover:text-emerald-300 hover:underline">
          S&apos;inscrire
        </Link>
      </p>
    </form>
  );
}