"use client";

import { ReactNode } from "react";
import { LucideIcon } from "lucide-react";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;      // bouton CTA optionnel
  className?: string;
};

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`text-center py-16 px-6 border-2 border-dashed border-border/60 rounded-2xl bg-background/30 ${className}`}
    >
      {/* Icône dans un cercle avec halo emerald subtil */}
      <div className="relative inline-flex mb-5">
        <div className="absolute inset-0 bg-emerald-500/10 blur-2xl rounded-full" />
        <div className="relative w-16 h-16 rounded-2xl bg-card/80 border border-border flex items-center justify-center">
          <Icon className="w-7 h-7 text-emerald-400/70" strokeWidth={1.5} />
        </div>
      </div>

      {/* Titre */}
      <h3 className="text-sm font-semibold text-foreground mb-1.5">{title}</h3>

      {/* Description */}
      <p className="text-xs text-muted-foreground max-w-sm mx-auto leading-relaxed">
        {description}
      </p>

      {/* Action optionnelle */}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}