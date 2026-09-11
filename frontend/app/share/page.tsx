"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertCircle, Bot, ImageOff, Loader2, User as UserIcon } from "lucide-react";

import { getPublicShare, type PublicConversationShare, type PublicMessage } from "@/lib/shares";
import { MarkdownRenderer } from "@/components/markdown_renderer";

// Page publique — AUCUNE authentification requise. Ne pas importer de
// composant/hook qui déclenche un appel authentifié en arrière-plan (voir
// le garde ajouté dans lib/api.ts pour /share/*, mais mieux vaut ne pas en
// avoir besoin du tout ici).
export default function PublicSharePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-background">
          <Loader2 className="animate-spin text-emerald-500" size={28} />
        </div>
      }
    >
      <PublicSharePageInner />
    </Suspense>
  );
}

function PublicSharePageInner() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [data, setData] = useState<PublicConversationShare | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!token) return;
    getPublicShare(token)
      .then(setData)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="animate-spin text-emerald-500" size={28} />
      </div>
    );
  }

  if (notFound || !data) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-background text-center px-4">
        <AlertCircle size={40} className="text-muted-foreground mb-4" />
        <h1 className="text-xl font-semibold text-foreground mb-2">
          Ce lien n&apos;est plus valide
        </h1>
        <p className="text-sm text-muted-foreground mb-6 max-w-sm">
          Le partage a peut-être été révoqué par son auteur, ou le lien est
          incorrect.
        </p>
        <Link
          href="/register"
          className="px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors"
        >
          Découvrir Vector
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="border-b border-border bg-background/80 backdrop-blur px-4 py-3 sticky top-0 z-10">
        <p className="text-sm text-muted-foreground text-center">
          Cette conversation a été partagée par{" "}
          <span className="text-foreground font-medium">{data.shared_by}</span>
        </p>
      </header>

      <main className="flex-1 w-full max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-lg font-semibold text-foreground mb-6">{data.title}</h1>
        <div className="space-y-4">
          {data.messages.map((m, i) => (
            <PublicMessageBubble key={i} message={m} />
          ))}
        </div>
      </main>

      <footer className="border-t border-border bg-background px-4 py-6 text-center">
        <p className="text-sm text-muted-foreground mb-3">Envie de discuter avec Vector ?</p>
        <Link
          href="/register"
          className="inline-block px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors"
        >
          Créer un compte
        </Link>
      </footer>
    </div>
  );
}

function PublicMessageBubble({ message }: { message: PublicMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`mt-0.5 p-1.5 rounded-full flex-shrink-0 ${
          isUser ? "bg-muted" : "bg-emerald-600/15"
        }`}
      >
        {isUser ? (
          <UserIcon size={14} className="text-muted-foreground" />
        ) : (
          <Bot size={14} className="text-emerald-400" />
        )}
      </div>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
          isUser
            ? "bg-emerald-600 text-white"
            : "bg-card border border-border text-foreground"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <MarkdownRenderer content={message.content} className="text-sm" />
        )}

        {message.attachments && message.attachments.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {message.attachments.map((att, i) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={i}
                src={att.preview_base64}
                alt={att.file_name}
                className="max-w-[200px] max-h-[200px] rounded-lg border border-border object-cover"
              />
            ))}
          </div>
        )}

        {message.has_hidden_attachments && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg bg-background/60 border border-border text-xs text-muted-foreground w-fit">
            <ImageOff size={14} />
            Image non partagée
          </div>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/60 space-y-1.5">
            {message.sources.map((s, i) => (
              <div key={i} className="text-xs text-muted-foreground">
                📄 {s.document_name}
                {s.page_number ? ` — p.${s.page_number}` : ""}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
