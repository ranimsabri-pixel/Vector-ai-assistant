"use client";

import {
  ArrowDown,
  ArrowUp,
  AlertCircle,
  BarChart,
  Calendar,
  CalendarClock,
  CheckCircle,
  Database,
  Hash,
  PieChart,
  Radio,
  Sparkles,
  Star,
  Tags,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

import { type KPISpec, type KPIResult } from "@/lib/datasets";

// Mapping iconographique : le backend donne un nom, on retourne le composant
const ICON_MAP: Record<string, LucideIcon> = {
  ArrowDown,
  ArrowUp,
  AlertCircle,
  BarChart,
  Calendar,
  CalendarClock,
  CheckCircle,
  Database,
  Hash,
  PieChart,
  Radio,
  Sparkles,
  Star,
  Tags,
  TrendingDown,
  TrendingUp,
};

const CATEGORY_COLORS: Record<string, string> = {
  volume: "from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400",
  average: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/30 text-emerald-400",
  range: "from-amber-500/20 to-amber-500/5 border-amber-500/30 text-amber-400",
  quality: "from-red-500/20 to-red-500/5 border-red-500/30 text-red-400",
  distribution: "from-purple-500/20 to-purple-500/5 border-purple-500/30 text-purple-400",
  ratio: "from-pink-500/20 to-pink-500/5 border-pink-500/30 text-pink-400",
  trend: "from-cyan-500/20 to-cyan-500/5 border-cyan-500/30 text-cyan-400",
  breakdown: "from-indigo-500/20 to-indigo-500/5 border-indigo-500/30 text-indigo-400",
  translated: "from-violet-500/20 to-violet-500/5 border-violet-500/30 text-violet-400",
  general: "from-muted-foreground/20 to-muted-foreground/5 border-border text-muted-foreground",
};

interface KpiNumberCardProps {
  spec: KPISpec;
  result: KPIResult;
}

export function KpiNumberCard({ spec, result }: KpiNumberCardProps) {
  const Icon = (spec.icon && ICON_MAP[spec.icon]) || Hash;
  const colorClasses = CATEGORY_COLORS[spec.category] || CATEGORY_COLORS.general;
  const [bgGradient, borderColor, iconColor] = colorClasses
    .split(" ")
    .reduce<string[]>(
      (acc, cls) => {
        if (cls.startsWith("from-") || cls.startsWith("to-")) acc[0] += " " + cls;
        else if (cls.startsWith("border-")) acc[1] = cls;
        else if (cls.startsWith("text-")) acc[2] = cls;
        return acc;
      },
      ["", "border-border", "text-muted-foreground"]
    );

  return (
    <div
      className={
        "relative bg-gradient-to-br " +
        bgGradient +
        " bg-card/50 border " +
        borderColor +
        " rounded-xl p-5 hover:shadow-lg transition-all overflow-hidden group"
      }
    >
      {/* Header : icône + titre */}
      <div className="flex items-start justify-between mb-4">
        <div className={"p-2 rounded-lg bg-background/50 " + iconColor}>
          <Icon size={18} />
        </div>
        {spec.unit && (
          <span className="text-xs text-muted-foreground uppercase tracking-wider font-medium">
            {spec.unit}
          </span>
        )}
      </div>

      {/* Valeur principale */}
      <div className="mb-2">
        <p className="text-3xl font-bold text-foreground tracking-tight">
          {result.formatted}
        </p>
      </div>

      {/* Titre + description */}
      <div>
        <h3 className="text-sm font-semibold text-foreground mb-1 line-clamp-1">
          {spec.title}
        </h3>
        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
          {spec.description}
        </p>
      </div>

      {/* Métadonnées si pertinentes */}
      {result.metadata && spec.type === "ratio" && (
        <div className="mt-3 pt-3 border-t border-border/50 text-[10px] text-muted-foreground">
          {String(result.metadata.matched)} sur {String(result.metadata.total)} lignes
        </div>
      )}
    </div>
  );
}