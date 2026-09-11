"use client";

import { useTheme } from "next-themes";

/**
 * Couleurs neutres pour les configs ApexCharts (SVG/canvas — ne peut pas
 * lire les CSS custom properties directement, contrairement aux classes
 * Tailwind). Memes valeurs hex que les tokens de globals.css.
 */
export interface ChartTheme {
  mode: "light" | "dark";
  axisColor: string;
  gridColor: string;
  labelColor: string;
  foreground: string;
  mutedForeground: string;
  /** fond des tooltips (= --card) */
  tooltipBg: string;
  /** emerald AA-safe selon le mode (700 en light, 400 en dark) */
  primary: string;
}

const DARK: ChartTheme = {
  mode: "dark",
  axisColor: "#27272a",
  gridColor: "#27272a",
  labelColor: "#a1a1aa",
  foreground: "#f4f4f5",
  mutedForeground: "#71717a",
  tooltipBg: "#18181b",
  primary: "#34d399",
};

const LIGHT: ChartTheme = {
  mode: "light",
  axisColor: "#e4e4e7",
  gridColor: "#e4e4e7",
  labelColor: "#52525b",
  foreground: "#18181b",
  mutedForeground: "#a1a1aa",
  tooltipBg: "#ffffff",
  primary: "#047857",
};

export function useChartTheme(): ChartTheme {
  const { resolvedTheme } = useTheme();
  return resolvedTheme === "light" ? LIGHT : DARK;
}
