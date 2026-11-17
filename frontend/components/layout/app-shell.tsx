"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Building2, Calculator, GitCompare, LayoutDashboard, Map, Menu, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "@/lib/api/client";
import type { CommunitySummary, MarketOverview } from "@/lib/api/types";
import { formatDate } from "@/lib/formatters";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/explorer", label: "Market Explorer", icon: Map },
  { href: "/valuation", label: "Property Valuation", icon: Calculator },
  { href: "/communities", label: "Communities", icon: Building2 },
  { href: "/compare", label: "Area Comparison", icon: GitCompare },
  { href: "/methodology", label: "Methodology", icon: BookOpen },
];

const TITLES: Record<string, string> = {
  "/dashboard": "Market Overview",
  "/explorer": "Market Explorer",
  "/valuation": "Property Valuation",
  "/communities": "Communities",
  "/compare": "Area Comparison",
  "/methodology": "Methodology",
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const overview = useQuery({ queryKey: ["overview"], queryFn: () => api<MarketOverview>("/api/market/overview") });
  const communities = useQuery({ queryKey: ["communities", "master"], queryFn: () => api<{ communities: CommunitySummary[] }>("/api/communities?kind=master_project") });
  const title = pathname.startsWith("/communities/") ? "Community Intelligence" : TITLES[pathname] ?? "Dubai Real Estate Intelligence";
  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (needle.length < 2) return [];
    return (communities.data?.communities ?? []).filter((community) => community.community_name.toLowerCase().includes(needle) || (needle === "downtown dubai" && community.community_name === "DownTown Dubai")).slice(0, 6);
  }, [communities.data, query]);

  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-slate-200 bg-white px-4 py-5 md:flex">
        <Brand />
        <Nav pathname={pathname} />
      </aside>
      {open ? (
        <div className="fixed inset-0 z-40 bg-slate-900/30 md:hidden" onClick={() => setOpen(false)}>
          <aside className="h-full w-72 border-r border-slate-200 bg-white p-4" onClick={(event) => event.stopPropagation()}>
            <div className="mb-4 flex justify-end">
              <button aria-label="Close navigation" className="rounded-lg p-2 text-slate-500" onClick={() => setOpen(false)}><X size={18} /></button>
            </div>
            <Brand />
            <Nav pathname={pathname} onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      ) : null}
      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur-xl md:px-8">
          <button aria-label="Open navigation" className="rounded-lg p-2 text-slate-600 md:hidden" onClick={() => setOpen(true)}><Menu size={18} /></button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-900">{title}</p>
            <p className="hidden text-xs text-slate-500 sm:block">Historical analytics, not a live market feed</p>
          </div>
          <div className="relative hidden w-64 lg:block">
            <Search className="pointer-events-none absolute top-2.5 left-3 text-slate-400" size={14} />
            <input aria-label="Search communities" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search communities" className="w-full rounded-full border border-slate-200 bg-white py-2 pr-3 pl-8 text-sm text-slate-800 outline-none focus:border-slate-400" />
            {matches.length ? (
              <div className="absolute mt-2 w-full rounded-2xl border border-slate-200 bg-white p-1 shadow-lg">
                {matches.map((community) => (
                  <Link key={community.community_id} href={`/communities/${community.community_id}`} onClick={() => setQuery("")} className="block rounded-xl px-3 py-2 text-sm text-slate-800 hover:bg-slate-50">
                    {community.community_name}
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
          <span className="hidden rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 sm:inline">Through {formatDate(overview.data?.date_max)}</span>
        </header>
        <main className="overflow-x-clip px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}

function Brand() {
  return (
    <Link href="/dashboard" className="mb-6 block">
      <p className="text-xs tracking-[0.22em] text-slate-400 uppercase">Dubai</p>
      <p className="text-lg font-semibold tracking-tight text-slate-900">Market Intelligence</p>
    </Link>
  );
}

function Nav({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-1 flex-col gap-1" aria-label="Primary">
      {NAV.map((item) => {
        const active = pathname === item.href || (item.href === "/communities" && pathname.startsWith("/communities/"));
        const Icon = item.icon;
        return (
          <Link key={item.href} href={item.href} onClick={onNavigate} className={cn("flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900", active && "bg-slate-900 text-white hover:bg-slate-900 hover:text-white")}>
            <Icon size={16} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
