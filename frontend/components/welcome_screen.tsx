"use client";

import { BarChart3, MessageSquare, Sparkles } from "lucide-react";

type WelcomeScreenProps = {
  open: boolean;
  loadingExample: boolean;
  onStartExample: () => void;
  onExploreMyself: () => void;
};

export function WelcomeScreen({
  open,
  loadingExample,
  onStartExample,
  onExploreMyself,
}: WelcomeScreenProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-3xl bg-card border border-border rounded-2xl shadow-2xl animate-message-in p-8 md:p-12 text-center">
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-3">
          <span className="text-foreground">Bienvenue dans </span>
          <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
            Vector
          </span>
          <span className="text-foreground"> !</span>
        </h1>
        <p className="text-muted-foreground text-base md:text-lg mb-10">
          Ton commando IA pour analyser tes données et documents
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10 text-left">
          <FeatureCard
            icon={MessageSquare}
            title="Discute avec tes documents"
            description="Upload un PDF, Word ou PowerPoint et pose-lui des questions"
          />
          <FeatureCard
            icon={BarChart3}
            title="Analyse tes données tabulaires"
            description="Importe un CSV/Excel et crée des dashboards interactifs"
          />
          <FeatureCard
            icon={Sparkles}
            title="Une IA vraiment utile"
            description="Réponses précises, sources citées, tout en français"
          />
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            type="button"
            onClick={onStartExample}
            disabled={loadingExample}
            className="w-full sm:w-auto px-6 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-sm font-medium text-white flex items-center justify-center gap-2 transition-colors shadow-lg shadow-emerald-900/30"
          >
            <Sparkles size={16} className={loadingExample ? "animate-pulse" : ""} />
            {loadingExample ? "Chargement..." : "Commencer avec un dataset d'exemple"}
          </button>
          <button
            type="button"
            onClick={onExploreMyself}
            disabled={loadingExample}
            className="w-full sm:w-auto px-6 py-3 bg-muted hover:bg-muted-foreground/10 disabled:opacity-50 rounded-xl text-sm font-medium text-foreground transition-colors"
          >
            Explorer par moi-même
          </button>
        </div>
      </div>
    </div>
  );
}

function FeatureCard(props: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  description: string;
}) {
  const Icon = props.icon;
  return (
    <div className="bg-background/50 border border-border rounded-xl p-5">
      <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-3">
        <Icon size={18} className="text-emerald-400" />
      </div>
      <h3 className="text-sm font-semibold text-foreground mb-1.5">{props.title}</h3>
      <p className="text-xs text-muted-foreground leading-relaxed">{props.description}</p>
    </div>
  );
}
