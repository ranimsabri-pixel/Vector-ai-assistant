"use client";

import { useState } from "react";
import Image from "next/image";
import {
  ChevronDown,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  Zap,
  Loader2,
  FileText,
  FolderOpen,
  Search,
  Pin,
  X,
} from "lucide-react";
import {
  useDiscussionsStore,
  type Discussion,
} from "@/lib/store/discussions";

// ============================================================
// Sous-composant — Ligne de discussion (extrait pour lisibilité)
// ============================================================

function DiscussionRow({
  d,
  isActive,
  isEditing,
  editValue,
  onSelect,
  onStartEdit,
  onEditValueChange,
  onCommitEdit,
  onCancelEdit,
  onDelete,
  onTogglePin,
}: {
  d: Discussion;
  isActive: boolean;
  isEditing: boolean;
  editValue: string;
  onSelect: () => void;
  onStartEdit: () => void;
  onEditValueChange: (v: string) => void;
  onCommitEdit: () => void;
  onCancelEdit: () => void;
  onDelete: () => void;
  onTogglePin: () => void;
}) {
  return (
    <div
      data-testid="discussion-row"
      onClick={onSelect}
      className={`group flex items-center gap-1 px-2 py-2 rounded-lg text-xs cursor-pointer transition-all ${
        isActive
          ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-300"
          : "border border-transparent hover:bg-card text-muted-foreground"
      }`}
    >
      {isEditing ? (
        <input
          type="text"
          value={editValue}
          onChange={(e) => onEditValueChange(e.target.value)}
          onBlur={onCommitEdit}
          onKeyDown={(e) => {
            if (e.key === "Enter") onCommitEdit();
            else if (e.key === "Escape") onCancelEdit();
          }}
          autoFocus
          onClick={(e) => e.stopPropagation()}
          className="flex-1 min-w-0 bg-background border border-emerald-500/50 rounded px-2 py-1 text-xs text-foreground focus:outline-none"
        />
      ) : (
        <span className="flex-1 min-w-0 truncate px-1 flex items-center gap-1.5">
          {d.corpusId ? (
            <FolderOpen size={11} className="text-blue-400 shrink-0" />
          ) : (
            d.documentName && (
              <FileText size={11} className="text-emerald-500 shrink-0" />
            )
          )}
          <span className="truncate">{d.title}</span>
          {d.pending && (
            <Loader2 size={10} className="animate-spin text-muted-foreground shrink-0" />
          )}
        </span>
      )}

      {/* Pin — toujours visible si épinglé, sinon au hover uniquement */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onTogglePin();
        }}
        className={`p-1 rounded transition-all ${
          d.isPinned
            ? "text-amber-400 opacity-100 hover:bg-muted"
            : "opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-foreground hover:bg-muted"
        }`}
        title={d.isPinned ? "Désépingler" : "Épingler"}
      >
        <Pin size={11} />
      </button>

      {/* Renommer — hover uniquement */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onStartEdit();
        }}
        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground transition-all"
        title="Renommer"
      >
        <Pencil size={11} />
      </button>

      {/* Supprimer — hover uniquement */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 rounded text-muted-foreground hover:text-red-400 transition-all"
        title="Supprimer"
      >
        <Trash2 size={11} />
      </button>
    </div>
  );
}

// ============================================================
// Composant principal AgentPanel
// ============================================================

export function AgentPanel() {
  const [capacitesOpen, setCapacitesOpen] = useState(true);
  const [actionsOpen, setActionsOpen] = useState(false);
  const [discussionsOpen, setDiscussionsOpen] = useState(true);

  const {
    discussions,
    activeId,
    searchQuery,
    addDiscussion,
    deleteDiscussion,
    setActive,
    renameDiscussion,
    togglePin,
    setSearchQuery,
  } = useDiscussionsStore();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  // ============================================================
  // Filtrage + groupement J27
  // ============================================================

  // 1. Filtrer par recherche (insensible à la casse)
  const filtered = searchQuery.trim()
    ? discussions.filter((d) =>
        d.title.toLowerCase().includes(searchQuery.trim().toLowerCase()),
      )
    : discussions;

  // 2. Séparer épinglées vs. non-épinglées
  const pinned = filtered.filter((d) => d.isPinned);
  const unpinned = filtered.filter((d) => !d.isPinned);

  // 3. Grouper les non-épinglées par période temporelle
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const sevenDaysAgo = new Date(today);
  sevenDaysAgo.setDate(today.getDate() - 7);

  const groupsByPeriod: {
    today: Discussion[];
    sevenDays: Discussion[];
    older: Discussion[];
  } = { today: [], sevenDays: [], older: [] };

  for (const d of unpinned) {
    const date = new Date(d.updatedAt || d.createdAt);
    if (date >= today) {
      groupsByPeriod.today.push(d);
    } else if (date >= sevenDaysAgo) {
      groupsByPeriod.sevenDays.push(d);
    } else {
      groupsByPeriod.older.push(d);
    }
  }

  // ============================================================
  // Helpers pour rendre une ligne (évite la répétition dans les sections)
  // ============================================================

  const renderRow = (d: Discussion) => (
    <DiscussionRow
      key={d.id}
      d={d}
      isActive={activeId === d.id}
      isEditing={editingId === d.id}
      editValue={editValue}
      onSelect={() => setActive(d.id)}
      onStartEdit={() => {
        setEditingId(d.id);
        setEditValue(d.title);
      }}
      onEditValueChange={setEditValue}
      onCommitEdit={() => {
        if (editValue.trim()) {
          renameDiscussion(d.id, editValue.trim());
        }
        setEditingId(null);
      }}
      onCancelEdit={() => setEditingId(null)}
      onDelete={() => {
        if (window.confirm(`Supprimer la discussion "${d.title}" ?`)) {
          deleteDiscussion(d.id);
        }
      }}
      onTogglePin={() => togglePin(d.id)}
    />
  );

  // ============================================================
  // Rendu
  // ============================================================

  return (
    <aside className="w-72 bg-background border-r border-border flex flex-col flex-shrink-0 relative">
      {/* Barre d'accent verticale verte avec glow */}
      <div
        className="absolute left-0 top-0 bottom-0 w-[3px] bg-emerald-500 z-10"
        style={{
          boxShadow:
            "0 0 8px rgba(45, 134, 89, 0.8), 0 0 16px rgba(45, 134, 89, 0.4)",
        }}
      />

      {/* Vector visual */}
      <div className="p-3">
        <div className="relative w-52 mx-auto aspect-[4/5] rounded-xl overflow-hidden">
          <Image
            src="/vector-avatar.png"
            alt="Vector"
            fill
            className="object-cover"
          />
          <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-background via-background/60 to-transparent pointer-events-none" />
        </div>

        <div className="mt-3 px-1">
          <h2 className="text-lg font-bold text-foreground">Vector</h2>
          <p className="text-xs text-muted-foreground">
            Commando IA Analyse de Données
          </p>
        </div>
      </div>

      {/* Sections collapsibles */}
      <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-2">
        <Section
          icon={<Sparkles size={14} className="text-emerald-400" />}
          title="Capacités Spéciales"
          open={capacitesOpen}
          onToggle={() => setCapacitesOpen(!capacitesOpen)}
        >
          <p>Dashboards KPI automatisés et configurables</p>
          <p>Analyses de performance marketing et commerciale</p>
          <p>Segmentation client RFM et recommandations</p>
        </Section>

        <Section
          icon={<Zap size={14} className="text-emerald-400" />}
          title="Actions Rapides"
          open={actionsOpen}
          onToggle={() => setActionsOpen(!actionsOpen)}
        >
          <p>Dashboard KPI général</p>
          <p>Analyse marketing</p>
          <p>Analyse commerciale</p>
          <p>Segmentation clients</p>
          <p>Tendances et anomalies</p>
        </Section>

        {/* ============================================================
            Discussions avec recherche + épinglage — J27
            ============================================================ */}
        <div className="border border-border rounded-lg overflow-hidden">
          <button
            onClick={() => setDiscussionsOpen(!discussionsOpen)}
            className="w-full flex items-center justify-between p-3 hover:bg-card/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-foreground">
                Discussions
              </span>
              {discussions.length > 0 && (
                <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-muted text-muted-foreground rounded-full">
                  {discussions.length}
                </span>
              )}
            </div>
            <ChevronDown
              size={14}
              className={`text-muted-foreground transition-transform ${
                discussionsOpen ? "rotate-180" : ""
              }`}
            />
          </button>

          {discussionsOpen && (
            <div className="px-3 pb-3 space-y-2">
              {/* Barre de recherche */}
              <div className="relative">
                <Search
                  size={12}
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
                />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Rechercher…"
                  className="w-full pl-7 pr-7 py-1.5 bg-background border border-border rounded-lg text-xs text-foreground placeholder-muted-foreground focus:outline-none focus:border-emerald-500/40"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    title="Effacer"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>

              {/* Bouton Nouvelle Discussion */}
              <button
                onClick={addDiscussion}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-emerald-600/10 hover:bg-emerald-600/20 border border-emerald-600/30 rounded-lg text-emerald-400 text-xs font-medium transition-colors"
              >
                <Plus size={14} />
                Nouvelle Discussion
              </button>

              {/* Liste avec sections */}
              {filtered.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-2 italic">
                  {searchQuery
                    ? "Aucun résultat"
                    : "Aucune discussion pour le moment"}
                </p>
              ) : (
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {/* Section Épinglées */}
                  {pinned.length > 0 && (
                    <div>
                      <div className="flex items-center gap-1.5 px-1 pb-1.5">
                        <Pin size={9} className="text-amber-400" />
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                          Épinglées
                        </span>
                      </div>
                      <div className="space-y-1">
                        {pinned.map(renderRow)}
                      </div>
                    </div>
                  )}

                  {/* Section Aujourd'hui */}
                  {groupsByPeriod.today.length > 0 && (
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold px-1 pb-1.5">
                        Aujourd&apos;hui
                      </p>
                      <div className="space-y-1">
                        {groupsByPeriod.today.map(renderRow)}
                      </div>
                    </div>
                  )}

                  {/* Section 7 derniers jours */}
                  {groupsByPeriod.sevenDays.length > 0 && (
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold px-1 pb-1.5">
                        7 derniers jours
                      </p>
                      <div className="space-y-1">
                        {groupsByPeriod.sevenDays.map(renderRow)}
                      </div>
                    </div>
                  )}

                  {/* Section Plus ancien */}
                  {groupsByPeriod.older.length > 0 && (
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold px-1 pb-1.5">
                        Plus ancien
                      </p>
                      <div className="space-y-1">
                        {groupsByPeriod.older.map(renderRow)}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

// ============================================================
// Sous-composant Section (inchangé)
// ============================================================

function Section({
  icon,
  title,
  open,
  onToggle,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 hover:bg-card/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm font-medium text-foreground">{title}</span>
        </div>
        <ChevronDown
          size={14}
          className={`text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-1.5 text-xs text-muted-foreground leading-relaxed">
          {children}
        </div>
      )}
    </div>
  );
}