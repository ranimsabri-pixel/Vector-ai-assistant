"use client";

import { useState } from "react";
import { Share2 } from "lucide-react";
import { usePathname } from "next/navigation";

import { useAuthStore } from "@/lib/store/auth";
import { useDiscussionsStore } from "@/lib/store/discussions";
import { ShareConversationModal } from "@/components/share-conversation-modal";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/user-menu";

export function Header() {
  const pathname = usePathname();
  const { user } = useAuthStore();
  const activeId = useDiscussionsStore((s) => s.activeId);
  const activeDiscussion = useDiscussionsStore((s) =>
    s.discussions.find((d) => d.id === s.activeId)
  );
  const [shareModalOpen, setShareModalOpen] = useState(false);

  if (!user) return null;

  // Le bouton Partager n'a de sens que sur la page de chat, avec une
  // conversation active ET deja persistee cote backend (pas un tempId
  // "pending" optimiste — POST /share sur un id inexistant echouerait).
  const canShare = pathname === "/" && !!activeId && !activeDiscussion?.pending;

  return (
    <header className="h-14 border-b border-border bg-background flex items-center justify-between px-4 flex-shrink-0">
      <div className="flex items-center gap-2">
        
      </div>

      <div className="flex items-center gap-1">
        {canShare && (
          <button
            onClick={() => setShareModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 mr-1 rounded-lg text-sm text-foreground hover:bg-card hover:text-foreground border border-border transition-colors"
            title="Partager cette conversation"
          >
            <Share2 size={16} />
            Partager
          </button>
        )}
        <ThemeToggle />
        <UserMenu />
      </div>

      {canShare && activeId && (
        <ShareConversationModal
          open={shareModalOpen}
          onClose={() => setShareModalOpen(false)}
          conversationId={activeId}
        />
      )}
    </header>
  );
}