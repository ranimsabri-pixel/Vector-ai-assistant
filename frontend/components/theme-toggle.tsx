"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

const CYCLE = ["light", "dark", "system"] as const;
type ThemeChoice = (typeof CYCLE)[number];

const ICONS: Record<ThemeChoice, typeof Sun> = {
  light: Sun,
  dark: Moon,
  system: Monitor,
};

const LABELS: Record<ThemeChoice, string> = {
  light: "Thème clair",
  dark: "Thème sombre",
  system: "Thème système",
};

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Le theme reel n'est connu qu'apres hydratation (evite le mismatch SSR).
  useEffect(() => setMounted(true), []);

  const current = (mounted ? (theme as ThemeChoice) : undefined) ?? "system";
  const Icon = ICONS[current];

  function cycle() {
    const next = CYCLE[(CYCLE.indexOf(current) + 1) % CYCLE.length];
    setTheme(next);
  }

  return (
    <button
      data-testid="theme-toggle"
      data-theme-current={current}
      onClick={cycle}
      className="p-2 hover:bg-secondary rounded-lg text-muted-foreground hover:text-foreground transition-colors"
      title={`${LABELS[current]} — cliquer pour changer`}
      aria-label="Changer de thème"
    >
      <Icon size={18} className="transition-transform duration-200" />
    </button>
  );
}
