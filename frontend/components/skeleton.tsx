export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={
        "bg-muted/50 rounded animate-pulse " + className
      }
    />
  );
}

export function DatasetCardSkeleton() {
  return (
    <div className="bg-card/50 border border-border rounded-xl p-4 flex items-start gap-3">
      <Skeleton className="w-10 h-10 rounded-lg flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-16" />
        </div>
        <Skeleton className="h-3 w-72" />
        <div className="flex gap-3 mt-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-24" />
        </div>
      </div>
    </div>
  );
}

export function DatasetListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <DatasetCardSkeleton key={i} />
      ))}
    </div>
  );
}
// ============================================================
// NEW J28 — Skeletons pour l'onglet Documents
// ============================================================

/**
 * Skeleton pour une carte de document PDF dans DocumentsList.
 * Reproduit la structure : badge PDF coloré + nom + status + métadonnées + 3 actions.
 */
export function DocumentCardSkeleton() {
  return (
    <div className="flex items-center gap-4 p-4 bg-card/50 border border-border rounded-xl">
      {/* Badge PDF */}
      <Skeleton className="w-10 h-10 rounded-lg flex-shrink-0" />

      {/* Nom + métadonnées */}
      <div className="flex-1 min-w-0 space-y-2">
        <Skeleton className="h-4 w-56 max-w-full" />
        <div className="flex items-center gap-2 flex-wrap">
          <Skeleton className="h-3 w-16 rounded" />
          <Skeleton className="h-3 w-14" />
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>

      {/* 3 boutons d'action à droite (Eye, MessageCircle, Trash2) */}
      <div className="flex items-center gap-1 flex-shrink-0">
        <Skeleton className="w-7 h-7 rounded-lg" />
        <Skeleton className="w-7 h-7 rounded-lg" />
        <Skeleton className="w-7 h-7 rounded-lg" />
      </div>
    </div>
  );
}

/** Rend plusieurs DocumentCardSkeleton — utile pour le loading initial. */
export function DocumentListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <DocumentCardSkeleton key={i} />
      ))}
    </div>
  );
}

// ============================================================
// NEW J36 — Skeletons pour la grille de SavedDashboard
// ============================================================

export function SavedDashboardCardSkeleton() {
  return (
    <div className="bg-card/50 border border-border rounded-xl p-5">
      <div className="flex items-start gap-3 mb-4">
        <Skeleton className="w-9 h-9 rounded-lg flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
      <Skeleton className="h-3 w-full mb-2" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  );
}

/** Rend plusieurs SavedDashboardCardSkeleton en grille — utile pour le loading initial. */
export function SavedDashboardListSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <SavedDashboardCardSkeleton key={i} />
      ))}
    </div>
  );
}