"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

const OPTIONS = [
  { value: "light", label: "Clair", icon: Sun },
  { value: "dark", label: "Sombre", icon: Moon },
  { value: "system", label: "Auto (système)", icon: Monitor },
] as const;

export function SettingsAppearance() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const current = mounted ? theme : undefined;

  return (
    <div>
      <h2 className="text-sm font-semibold text-foreground mb-1">Thème</h2>
      <p className="text-sm text-muted-foreground mb-4">
        Le thème choisi est appliqué immédiatement et mémorisé sur cet appareil.
      </p>

      <div role="radiogroup" aria-label="Thème" className="grid grid-cols-3 gap-3 max-w-lg">
        {OPTIONS.map(({ value, label, icon: Icon }) => {
          const active = current === value;
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => setTheme(value)}
              className={`flex flex-col items-center gap-2 px-4 py-4 rounded-xl border text-sm font-medium transition-colors ${
                active
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:text-foreground hover:bg-card"
              }`}
            >
              <Icon size={20} />
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
