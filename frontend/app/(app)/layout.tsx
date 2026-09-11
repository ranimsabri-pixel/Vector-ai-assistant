"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { Toaster, toast } from "sonner";

import { AgentPanel } from "@/components/agent-panel";
import { Header } from "@/components/header";
import { IconSidebar } from "@/components/icon-sidebar";
import { PdfViewerPanel } from "@/components/pdf_viewer_panel";
import { WelcomeScreen } from "@/components/welcome_screen";
import { OnboardingTour, ONBOARDING_TOUR_STEPS } from "@/components/onboarding_tour";
import { useAuthStore } from "@/lib/store/auth";
import { usePdfViewerStore } from "@/lib/hooks/use-pdf-viewer";
import {
  completeOnboarding,
  getOnboardingStatus,
  loadExampleDataset,
} from "@/lib/onboarding";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { resolvedTheme } = useTheme();
  const { isAuthenticated, hasHydrated, token } = useAuthStore();
  const isPdfPanelOpen = usePdfViewerStore((s) => s.isOpen);

  const [showWelcome, setShowWelcome] = useState(false);
  const [loadingExample, setLoadingExample] = useState(false);
  const [tourStep, setTourStep] = useState<number | null>(null);

  useEffect(() => {
    // Attend la rehydratation du store persist (lecture du token en
    // localStorage) avant de decider de rediriger — sinon un rechargement
    // direct sur une page protegee renvoie systematiquement au login, meme
    // avec une session valide.
    if (hasHydrated && !isAuthenticated) {
      router.push("/login");
    }
  }, [hasHydrated, isAuthenticated, router]);

  useEffect(() => {
    if (!hasHydrated || !isAuthenticated || !token) return;
    getOnboardingStatus(token)
      .then((status) => {
        if (status.is_new) setShowWelcome(true);
      })
      .catch(() => {
        // Silencieux : l'onboarding n'est qu'un bonus, ne doit jamais bloquer l'app
      });
  }, [hasHydrated, isAuthenticated, token]);

  async function handleStartExample() {
    if (!token) return;
    setLoadingExample(true);
    try {
      const dataset = await loadExampleDataset(token);
      await completeOnboarding(token);
      setShowWelcome(false);
      toast.success("Dataset d'exemple chargé — profilage en cours");
      router.push(`/datasets/view?id=${dataset.id}`);
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Erreur de chargement du dataset d'exemple",
      );
    } finally {
      setLoadingExample(false);
    }
  }

  async function handleExploreMyself() {
    if (!token) return;
    setShowWelcome(false);
    setTourStep(0);
    try {
      await completeOnboarding(token);
    } catch {
      // Non bloquant : le tour se lance meme si le flag n'a pas pu etre sauvegarde
    }
  }

  function handleTourNext() {
    setTourStep((s) => {
      if (s === null) return null;
      if (s >= ONBOARDING_TOUR_STEPS - 1) return null;
      return s + 1;
    });
  }

  function handleTourSkip() {
    setTourStep(null);
  }

  if (!hasHydrated || !isAuthenticated) {
    return null;
  }

  return (
    <div className="flex h-screen bg-background text-foreground">
      <IconSidebar />
      <AgentPanel />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-hidden">
          <div
            className={`grid h-full transition-[grid-template-columns] duration-300 ${
              isPdfPanelOpen ? "grid-cols-[3fr_2fr]" : "grid-cols-[1fr]"
            }`}
          >
            <div className="h-full overflow-hidden min-w-0">{children}</div>
            {isPdfPanelOpen && <PdfViewerPanel />}
          </div>
        </main>
      </div>

      {/* NEW J28.C — Toaster global (sonner) */}
      <Toaster
        theme={resolvedTheme === "light" ? "light" : "dark"}
        position="bottom-right"
        richColors
        closeButton
        toastOptions={{
          style: {
            background: "var(--card)",
            border: "1px solid var(--border)",
            color: "var(--card-foreground)",
          },
        }}
      />

      {/* NEW J40.B — Onboarding nouveaux utilisateurs */}
      <WelcomeScreen
        open={showWelcome}
        loadingExample={loadingExample}
        onStartExample={handleStartExample}
        onExploreMyself={handleExploreMyself}
      />
      <OnboardingTour step={tourStep} onNext={handleTourNext} onSkip={handleTourSkip} />
    </div>
  );
}