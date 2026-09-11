"use client";

import { Globe } from "lucide-react";
import type { WebSource } from "@/lib/web_search";

type WebSourceCardProps = {
  source: WebSource;
  index: number;
};

export function WebSourceCard({ source, index }: WebSourceCardProps) {
  let hostname = source.url;
  try {
    hostname = new URL(source.url).hostname.replace(/^www\./, "");
  } catch {
    // URL invalide — on garde l'URL brute
  }

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group text-left px-3 py-2 rounded-lg bg-card/60 border border-border hover:border-emerald-700/60 hover:bg-card transition min-w-0 w-full block"
    >
      <div className="flex items-start gap-2">
        <div className="w-6 h-6 rounded flex items-center justify-center shrink-0 bg-emerald-600">
          <Globe className="w-3 h-3 text-white" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <span className="text-[11px] font-semibold text-emerald-400">
              [{index + 1}] Source web
            </span>
          </div>
          <p className="text-xs font-medium text-foreground truncate group-hover:text-emerald-300 transition-colors">
            {source.title || hostname}
          </p>
          <p className="text-[10px] text-muted-foreground truncate mb-1">{hostname}</p>
          <p className="text-[11px] text-muted-foreground leading-snug line-clamp-2">
            {source.snippet}
          </p>
        </div>
      </div>
    </a>
  );
}
