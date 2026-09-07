"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3, BellRing, Building2, ClipboardCheck, FilePlus2, FolderKanban,
  Home, Landmark, ListChecks, ShieldCheck,
} from "lucide-react";
import { ScopeSelector } from "./scope-selector";
import { useScope } from "@/lib/scope";

const ROLE_LINKS = {
  MP: [
    { href: "/", label: "Home", icon: Home },
    { href: "/recommend-work", label: "Recommend Work", icon: FilePlus2 },
    { href: "/my-works", label: "My Works", icon: FolderKanban },
    { href: "/alerts", label: "Alerts", icon: BellRing },
  ],
  DISTRICT: [
    { href: "/", label: "Home", icon: Home },
    { href: "/new-recommendations", label: "New Recommendations", icon: ListChecks },
    { href: "/review-queue?review_need=ALL", label: "Active Works", icon: FolderKanban },
    { href: "/review-queue", label: "Review Queue", icon: ClipboardCheck },
    { href: "/#compliance-issues", label: "Compliance", icon: ShieldCheck },
    { href: "/alerts", label: "Alerts", icon: BellRing },
  ],
  STATE: [
    { href: "/", label: "Home", icon: Home },
    { href: "/#district-comparison", label: "Districts", icon: Building2 },
    { href: "/review-queue", label: "Review Queue", icon: ClipboardCheck },
    { href: "/trends", label: "Trends", icon: BarChart3 },
    { href: "/alerts", label: "Alerts", icon: BellRing },
  ],
  MOSPI: [
    { href: "/", label: "National Overview", icon: Building2 },
    { href: "/review-queue", label: "Review Queue", icon: ClipboardCheck },
    { href: "/#state-comparison", label: "States", icon: Landmark },
    { href: "/trends", label: "Trends", icon: BarChart3 },
    { href: "/alerts", label: "Alerts", icon: BellRing },
  ],
  IA: [
    { href: "/", label: "Home", icon: Home },
    { href: "/review-queue", label: "Active Works", icon: FolderKanban },
    { href: "/alerts", label: "Alerts", icon: BellRing },
  ],
};

const ROLE_HEADERS = {
  MP: "MP Portal", DISTRICT: "District Authority", STATE: "State Authority",
  MOSPI: "MoSPI", IA: "Implementing Agency",
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { scope } = useScope();
  const links = ROLE_LINKS[scope.role];
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Landmark size={21} /></div>
        <div><strong>TRACE-X KAVACH</strong><span>MPLADS Monitoring &amp; Management Platform</span></div></div>
      <nav aria-label="Primary navigation">{links.map(({ href, label, icon: Icon }) =>
        <Link key={href} href={href} className={pathname === href || (href !== "/" && pathname.startsWith(href)) ? "nav-link active" : "nav-link"}>
          <Icon size={18} /><span>{label}</span>
        </Link>)}</nav>
      <div className="sidebar-note"><ShieldCheck size={17} /><p><strong>Human review required</strong><br />Signals prioritize attention; they do not establish a finding.</p></div>
    </aside>
    <div className="main-column">
      <header className="topbar"><div><p className="eyebrow">{ROLE_HEADERS[scope.role]}</p><h1>MPLADS Monitoring &amp; Management Platform</h1></div><ScopeSelector /></header>
      <main className="content">{children}</main>
      <footer>TRACE-X KAVACH · Track works, review issues, and take action from one place.</footer>
    </div>
  </div>;
}
