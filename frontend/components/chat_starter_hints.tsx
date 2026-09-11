"use client";

import { Sparkles } from "lucide-react";

const EXAMPLES = [
  "Quels sont les datasets que j'ai importés ?",
  "Compare-moi les ventes par région dans mon dataset",
  "Résume le PDF que je viens d'uploader",
];

type ChatStarterHintsProps = {
  onPick: (question: string) => void;
};

export function ChatStarterHints({ onPick }: ChatStarterHintsProps) {
  return (
    <div className="text-center py-8">
      <Sparkles size={28} className="text-emerald-400 mx-auto mb-4" />
      <h2 className="text-lg font-semibold text-foreground mb-5">
        Comment poser une bonne question à Vector ?
      </h2>

      <div className="flex flex-col items-center gap-2.5 max-w-md mx-auto">
        {EXAMPLES.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => onPick(question)}
            className="w-full text-left px-4 py-2.5 bg-card border border-border hover:border-emerald-600/50 hover:bg-card/80 rounded-xl text-sm text-foreground transition-colors"
          >
            {question}
          </button>
        ))}
      </div>

      <p className="text-xs text-muted-foreground mt-6">
        Astuce : uploade un PDF avec le trombone pour l&apos;interroger directement
      </p>
    </div>
  );
}
