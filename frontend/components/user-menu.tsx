"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut, Settings } from "lucide-react";

import { useAuthStore } from "@/lib/store/auth";

export function UserMenu() {
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  if (!user) return null;

  const initials = (user.full_name || user.email)
    .split(/\s+|@/)
    .map((s) => s.charAt(0).toUpperCase())
    .slice(0, 2)
    .join("");

  function handleLogout() {
    setOpen(false);
    logout();
    router.push("/login");
  }

  function handleSettings() {
    setOpen(false);
    router.push("/settings");
  }

  return (
    <div className="relative ml-1" ref={containerRef}>
      <button
        data-testid="user-menu-trigger"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 p-1 pr-1.5 hover:bg-card rounded-lg transition-colors"
        title={user.full_name || user.email}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-sm font-semibold text-white ring-2 ring-emerald-500/30">
          {initials}
        </div>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-2 w-64 bg-card border border-border rounded-xl shadow-2xl overflow-hidden animate-message-in z-50"
        >
          <div className="px-4 py-3 border-b border-border">
            <p className="text-sm font-medium text-foreground truncate">
              {user.full_name || "Utilisateur"}
            </p>
            <p className="text-xs text-muted-foreground truncate">{user.email}</p>
          </div>
          <div className="p-1.5">
            <button
              role="menuitem"
              onClick={handleSettings}
              className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-foreground hover:bg-muted transition-colors"
            >
              <Settings size={16} className="text-muted-foreground" />
              Paramètres
            </button>
            <button
              role="menuitem"
              onClick={handleLogout}
              className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-red-400 hover:bg-red-950/30 transition-colors"
            >
              <LogOut size={16} />
              Se déconnecter
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
