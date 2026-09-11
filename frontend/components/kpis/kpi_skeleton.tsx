"use client";

/**
 * Skeleton loader pour le dashboard pendant la génération.
 * Affiche des cartes "fantômes" qui pulsent pour donner l'impression
 * que le contenu est déjà là, juste en cours de chargement.
 */
export function KpiDashboardSkeleton() {
  return (
    <div className="space-y-8 animate-pulse">
      {/* En-tête skeleton */}
      <div className="space-y-2">
        <div className="h-3 w-32 bg-muted rounded" />
        <div className="h-8 w-64 bg-muted rounded" />
        <div className="h-3 w-96 bg-muted rounded" />
      </div>

      {/* Section Indicateurs clés */}
      <section>
        <div className="h-3 w-24 bg-muted rounded mb-3" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <KpiCardSkeleton key={i} delay={i * 80} />
          ))}
        </div>
      </section>

      {/* Section Analyses visuelles */}
      <section>
        <div className="h-3 w-32 bg-muted rounded mb-3" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ChartSkeleton delay={500} />
          <ChartSkeleton delay={600} />
        </div>
      </section>
    </div>
  );
}

function KpiCardSkeleton({ delay = 0 }: { delay?: number }) {
  return (
    <div
      className="bg-card/50 border border-border rounded-xl p-5 space-y-3"
      style={{ animationDelay: delay + "ms" }}
    >
      <div className="flex items-center justify-between">
        <div className="h-8 w-8 bg-muted rounded-lg" />
        <div className="h-3 w-12 bg-muted rounded" />
      </div>
      <div className="h-8 w-24 bg-muted rounded" />
      <div className="space-y-2">
        <div className="h-3 w-full bg-muted rounded" />
        <div className="h-3 w-2/3 bg-muted rounded" />
      </div>
    </div>
  );
}

function ChartSkeleton({ delay = 0 }: { delay?: number }) {
  return (
    <div
      className="bg-card/50 border border-border rounded-xl p-5 space-y-4"
      style={{ animationDelay: delay + "ms" }}
    >
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 bg-muted rounded-lg" />
        <div className="space-y-2 flex-1">
          <div className="h-4 w-48 bg-muted rounded" />
          <div className="h-3 w-64 bg-muted rounded" />
        </div>
      </div>
      <div className="h-[260px] bg-muted/50 rounded" />
    </div>
  );
}