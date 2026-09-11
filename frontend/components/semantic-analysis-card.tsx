"use client";

import { Brain, Sparkles, AlertTriangle, TrendingUp } from "lucide-react";

import { type SemanticAnalysis, type SuggestedKPI } from "@/lib/datasets";

const DOMAIN_COLORS: Record<string, string> = {
  crm: "from-blue-500 to-cyan-500",
  marketing: "from-pink-500 to-rose-500",
  sales: "from-emerald-500 to-teal-500",
  finance: "from-amber-500 to-orange-500",
  hr: "from-purple-500 to-violet-500",
  ecommerce: "from-indigo-500 to-blue-500",
  operations: "from-zinc-500 to-zinc-600",
  other: "from-zinc-500 to-zinc-600",
};

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-red-500/10 text-red-400 border-red-500/30",
  medium: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  low: "bg-muted text-muted-foreground border-border",
};

const PRIORITY_LABELS: Record<string, string> = {
  high: "Priorité haute",
  medium: "Priorité moyenne",
  low: "Priorité basse",
};

interface SemanticAnalysisCardProps {
  analysis: SemanticAnalysis;
}

export function SemanticAnalysisCard({ analysis }: SemanticAnalysisCardProps) {
  const llm = analysis.llm_analysis;
  const gradient = DOMAIN_COLORS[llm.domain] || DOMAIN_COLORS.other;

  return (
    <div className="bg-card/50 rounded-xl border border-border overflow-hidden mb-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className={"relative bg-gradient-to-r " + gradient + " px-6 py-5"}>
        <div className="absolute inset-0 bg-black/40" />
        <div className="relative flex items-center gap-3">
          <div className="p-2 rounded-lg bg-white/10 backdrop-blur-sm border border-white/20">
            <Brain size={20} className="text-white" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider text-white/70 font-semibold mb-0.5">
              Analyse sémantique Vector
            </p>
            <h2 className="text-lg font-bold text-white">{llm.domain_label}</h2>
          </div>
        </div>
      </div>

      <div className="px-6 py-5 border-b border-border">
        <p className="text-sm text-foreground leading-relaxed">
          {llm.description}
        </p>
      </div>

      {llm.key_columns.length > 0 && (
        <div className="px-6 py-4 border-b border-border">
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
            Colonnes clés identifiées
          </p>
          <div className="flex flex-wrap gap-2">
            {llm.key_columns.map((col) => (
              <span
                key={col}
                className="px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-md text-xs text-emerald-300 font-mono"
              >
                {col}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="px-6 py-5">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={16} className="text-emerald-400" />
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">
            KPIs recommandés ({llm.suggested_kpis.length})
          </p>
        </div>
        <div className="space-y-3">
          {llm.suggested_kpis.map((kpi, i) => (
            <KpiCard key={i} kpi={kpi} />
          ))}
        </div>
      </div>

      {llm.warnings.length > 0 && (
        <div className="px-6 py-4 border-t border-border bg-amber-500/5">
          <div className="flex items-start gap-2">
            <AlertTriangle
              size={14}
              className="text-amber-400 flex-shrink-0 mt-0.5"
            />
            <div className="text-xs text-amber-300 space-y-1">
              {llm.warnings.map((w, i) => (
                <p key={i}>{w}</p>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function KpiCard({ kpi }: { kpi: SuggestedKPI }) {
  const priorityStyle =
    PRIORITY_STYLES[kpi.priority] || PRIORITY_STYLES.medium;
  const priorityLabel =
    PRIORITY_LABELS[kpi.priority] || PRIORITY_LABELS.medium;

  return (
    <div className="bg-background/50 border border-border rounded-lg p-4 hover:border-border transition-colors">
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Sparkles size={14} className="text-emerald-400 flex-shrink-0" />
          {kpi.name}
        </h3>
        <span
          className={
            "px-2 py-0.5 rounded text-[10px] font-medium border uppercase tracking-wider " +
            priorityStyle
          }
        >
          {priorityLabel}
        </span>
      </div>
      <p className="text-xs text-muted-foreground leading-relaxed mb-2">
        {kpi.description}
      </p>
      <div className="flex flex-wrap gap-1">
        {kpi.columns_used.map((col) => (
          <span
            key={col}
            className="px-1.5 py-0.5 bg-muted/50 border border-border rounded text-[10px] text-muted-foreground font-mono"
          >
            {col}
          </span>
        ))}
      </div>
    </div>
  );
}