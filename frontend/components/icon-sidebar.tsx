"use client";

import {
  Briefcase,
  ChevronsLeft,
  Database,
  Home,
  LayoutDashboard,
  MessagesSquare,
  Shield,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function IconSidebar() {
  const pathname = usePathname();

  return (
    <aside
      data-tour="sidebar"
      className="w-14 bg-background border-r border-border flex flex-col items-center py-3 flex-shrink-0"
    >
      <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-[10px] font-bold text-white tracking-wider shadow-lg shadow-emerald-900/40 mb-1">
        AIC
      </div>

      <button
        className="p-1.5 mb-4 rounded text-muted-foreground hover:text-muted-foreground transition-colors"
        title="Réduire la barre latérale"
        aria-label="Réduire la barre latérale"
      >
        <ChevronsLeft size={16} />
      </button>

      <nav className="flex flex-col items-center gap-1">
        <NavItem href="/" icon={<Home size={20} />} active={pathname === "/"} title="Accueil" />
        <NavItem href="#" icon={<Shield size={20} />} active={false} title="Profil" />
        <NavItem href="/" icon={<MessagesSquare size={20} />} active={pathname === "/"} title="Chat" />
        <NavItem
          href="/datasets"
          icon={<Database size={20} />}
          active={pathname.startsWith("/datasets")}
          title="Mes données"
          tourId="data-nav"
        />
        <NavItem
          href="/dashboards"
          icon={<LayoutDashboard size={20} />}
          active={pathname.startsWith("/dashboards") || pathname.startsWith("/saved-dashboards")}
          title="Mes dashboards"
        />
        <NavItem
          href="/personas"
          icon={<Sparkles size={20} />}
          active={pathname.startsWith("/personas")}
          title="Mes personas"
        />
        <NavItem href="#" icon={<Briefcase size={20} />} active={false} title="Workspace" />
      </nav>
    </aside>
  );
}

function NavItem({
  href,
  icon,
  active,
  title,
  tourId,
}: {
  href: string;
  icon: React.ReactNode;
  active: boolean;
  title: string;
  tourId?: string;
}) {
  return (
    <Link
      href={href}
      title={title}
      data-tour={tourId}
      className={
        active
          ? "p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/30 transition-colors"
          : "p-2.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-card transition-colors"
      }
    >
      {icon}
    </Link>
  );
}