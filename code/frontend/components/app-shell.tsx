"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, BellRing, ClipboardCheck, LayoutDashboard, Landmark, ShieldCheck } from "lucide-react";
import { ScopeSelector } from "./scope-selector";

const links = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/review-queue", label: "Review queue", icon: ClipboardCheck },
  { href: "/alerts", label: "Alert center", icon: BellRing },
  { href: "/trends", label: "Trends & hotspots", icon: BarChart3 },
  { href: "/methodology", label: "Methodology", icon: ShieldCheck },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Landmark size={21} /></div>
        <div><strong>MPLADS Sentinel</strong><span>Monitoring & decision support</span></div></div>
      <nav aria-label="Primary navigation">{links.map(({ href, label, icon: Icon }) =>
        <Link key={href} href={href} className={pathname === href || (href !== "/" && pathname.startsWith(href)) ? "nav-link active" : "nav-link"}>
          <Icon size={18} /><span>{label}</span>
        </Link>)}</nav>
      <div className="sidebar-note"><ShieldCheck size={17} /><p><strong>Human review required</strong><br />Signals prioritize attention; they do not establish a finding.</p></div>
    </aside>
    <div className="main-column">
      <header className="topbar"><div><p className="eyebrow">Government decision-support prototype</p><h1>AI-Powered Monitoring & Decision Support</h1></div><ScopeSelector /></header>
      <main className="content">{children}</main>
      <footer>Prototype data snapshot · 01 September 2026 · No automated decisions</footer>
    </div>
  </div>;
}
