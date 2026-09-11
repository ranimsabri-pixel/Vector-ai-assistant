"use client";

import { ReactNode } from "react";

// ============================================================
// Types
// ============================================================

type TabDef<T extends string> = {
  id: T;
  label: string;
  count?: number;
};

type TabsProps<T extends string> = {
  tabs: TabDef<T>[];
  active: T;
  onChange: (id: T) => void;
};

// ============================================================
// Composant Tabs — barre de navigation entre onglets
// ============================================================

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: TabsProps<T>) {
  return (
    <div className="border-b border-border flex gap-1">
      {tabs.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              isActive
                ? "border-emerald-500 text-emerald-400"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span
                className={`ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  isActive
                    ? "bg-emerald-950/60 text-emerald-300"
                    : "bg-card text-muted-foreground"
                }`}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ============================================================
// Composant TabPanel — contenu associé à un onglet
// ============================================================

type TabPanelProps = {
  active: string;
  value: string;
  children: ReactNode;
};

export function TabPanel({ active, value, children }: TabPanelProps) {
  if (active !== value) return null;
  return <div className="pt-6">{children}</div>;
}