"use client";

import {
  Bot, Sparkles, Briefcase, LineChart, TrendingUp, Users,
  MessageCircle, PieChart, BarChart3, Target, Lightbulb, Rocket,
  Building2, Calculator, FileText, Search, Globe, ShoppingCart,
  DollarSign, Megaphone, HeartHandshake, GraduationCap, Scale,
  Stethoscope, Code, Database, Newspaper, Compass, Award, Brain,
  type LucideIcon,
  type LucideProps,
} from "lucide-react";

// Doit rester synchro avec PERSONA_ICONS (lib/personas.ts) et
// ALLOWED_ICONS (backend app/schemas/persona.py).
export const PERSONA_ICON_MAP: Record<string, LucideIcon> = {
  Bot, Sparkles, Briefcase, LineChart, TrendingUp, Users,
  MessageCircle, PieChart, BarChart3, Target, Lightbulb, Rocket,
  Building2, Calculator, FileText, Search, Globe, ShoppingCart,
  DollarSign, Megaphone, HeartHandshake, GraduationCap, Scale,
  Stethoscope, Code, Database, Newspaper, Compass, Award, Brain,
};

type PersonaIconProps = LucideProps & { name: string };

export function PersonaIcon({ name, ...props }: PersonaIconProps) {
  const Icon = PERSONA_ICON_MAP[name] ?? Bot;
  return <Icon {...props} />;
}
