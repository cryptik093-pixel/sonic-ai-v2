"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const navigationItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/uploads", label: "Uploads" },
  { href: "/analysis", label: "Analysis" },
  { href: "/mastering", label: "Mastering" },
  { href: "/midi", label: "MIDI Studio" },
  { href: "/agent", label: "Agent" },
  { href: "/settings", label: "Settings" },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="studio-shell">
      <aside className="studio-sidebar" aria-label="Primary navigation">
        <Link className="studio-brand" href="/dashboard" aria-label="Sonic AI V2 dashboard">
          <span className="studio-brand-mark">S</span>
          <span>
            <strong>Sonic AI</strong>
            <small>V2 Studio</small>
          </span>
        </Link>

        <nav className="sidebar-nav">
          {navigationItems.map((item) => {
            const active = pathname === item.href || (item.href !== "/dashboard" && pathname?.startsWith(item.href));
            return (
              <Link aria-current={active ? "page" : undefined} className={active ? "active" : ""} href={item.href} key={item.href}>
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="studio-main">
        <header className="studio-topbar">
          <div>
            <span className="topbar-label">Project</span>
            <strong>Untitled production session</strong>
          </div>
          <div className="topbar-actions">
            <Link className="ghost-link" href="/uploads">
              Upload
            </Link>
            <Link className="primary-link compact" href="/analysis">
              Analyze
            </Link>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
