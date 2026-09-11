"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

type TourStepDef = {
  selector: string;
  text: string;
};

const STEPS: TourStepDef[] = [
  {
    selector: '[data-tour="sidebar"]',
    text: "Ici tu retrouves tes conversations, tes documents et tes tableaux de bord",
  },
  {
    selector: '[data-tour="chat-input"]',
    text: "Pose une question à Vector — il répond en français avec des sources",
  },
  {
    selector: '[data-tour="attach-button"]',
    text: "Uploade un PDF, Word ou PowerPoint pour l'interroger directement",
  },
  {
    selector: '[data-tour="data-nav"]',
    text: "Retrouve tes datasets et crée des dashboards personnalisés",
  },
];

export const ONBOARDING_TOUR_STEPS = STEPS.length;

type OnboardingTourProps = {
  step: number | null; // null = tour inactif, 0..STEPS.length-1 sinon
  onNext: () => void;
  onSkip: () => void;
};

export function OnboardingTour({ step, onNext, onSkip }: OnboardingTourProps) {
  const [rect, setRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (step === null) return;
    const selector = STEPS[step].selector;

    function measure() {
      const el = document.querySelector(selector);
      setRect(el ? el.getBoundingClientRect() : null);
    }

    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [step]);

  if (step === null) return null;

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;
  const pad = 8;

  const highlightStyle: React.CSSProperties = rect
    ? {
        top: rect.top - pad,
        left: rect.left - pad,
        width: rect.width + pad * 2,
        height: rect.height + pad * 2,
      }
    : { display: "none" };

  const viewportW = typeof window !== "undefined" ? window.innerWidth : 1280;
  const viewportH = typeof window !== "undefined" ? window.innerHeight : 800;
  const tooltipWidth = 320;
  const estimatedTooltipHeight = 160;

  // Les cibles tres hautes (ex: la sidebar pleine hauteur) n'ont pas de "en
  // dessous" qui reste dans le viewport : on positionne alors le tooltip a
  // cote (droite, ou gauche s'il n'y a pas la place) plutot qu'au-dessus/en dessous.
  const rectIsTall = !!rect && rect.height > viewportH * 0.5;

  let tooltipTop: number;
  let tooltipLeft: number;

  if (!rect) {
    tooltipTop = viewportH / 2 - estimatedTooltipHeight / 2;
    tooltipLeft = viewportW / 2 - tooltipWidth / 2;
  } else if (rectIsTall) {
    tooltipLeft = rect.right + pad + 12;
    if (tooltipLeft + tooltipWidth > viewportW - 16) {
      tooltipLeft = Math.max(16, rect.left - pad - 12 - tooltipWidth);
    }
    tooltipTop = Math.min(
      Math.max(rect.top, 16),
      viewportH - estimatedTooltipHeight - 16,
    );
  } else {
    const placeBelow = rect.bottom + estimatedTooltipHeight + 24 < viewportH;
    tooltipTop = placeBelow
      ? rect.bottom + pad + 12
      : Math.max(16, rect.top - pad - 12 - estimatedTooltipHeight);
    tooltipLeft = Math.min(Math.max(rect.left, 16), viewportW - tooltipWidth - 16);
  }

  return (
    <div className="fixed inset-0 z-[200]">
      {/* Backdrop — cliquable pour passer le tour, ne bloque jamais la navigation */}
      <div
        className="absolute inset-0 bg-black/60 animate-fade-in"
        onClick={onSkip}
      />

      {/* Highlight visuel de la zone ciblee */}
      {rect && (
        <div
          className="absolute rounded-xl ring-2 ring-emerald-500 shadow-[0_0_0_9999px_rgba(0,0,0,0.6)] pointer-events-none transition-all duration-300"
          style={highlightStyle}
        />
      )}

      {/* Tooltip */}
      <div
        className="absolute bg-card border border-border rounded-xl shadow-2xl p-4 pointer-events-auto"
        style={{
          top: tooltipTop,
          left: tooltipLeft,
          width: tooltipWidth,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2 mb-2">
          <span className="text-[10px] uppercase tracking-wider text-emerald-400 font-semibold">
            Étape {step + 1} / {STEPS.length}
          </span>
          <button
            type="button"
            onClick={onSkip}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Passer le tour"
          >
            <X size={14} />
          </button>
        </div>
        <p className="text-sm text-foreground mb-4">{current.text}</p>
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={onSkip}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Passer le tour
          </button>
          <button
            type="button"
            onClick={onNext}
            className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-xs font-medium text-white transition-colors"
          >
            {isLast ? "Terminer" : "Suivant"}
          </button>
        </div>
      </div>
    </div>
  );
}
