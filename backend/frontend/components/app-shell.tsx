"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useCallback, useEffect, useState } from "react";
import { Badge, Button, LinkButton, cx } from "@/components/ui";
import { clearSession, getCurrentUser, getToken, request, type User } from "@/lib/auth";

type NavItem = { href: string; label: string; premium?: boolean };

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Overview" },
  { href: "/applications", label: "Applications", premium: true },
  { href: "/career", label: "Career intelligence", premium: true },
];

export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    getCurrentUser()
      .then(setUser)
      .catch(() => {
        clearSession();
        router.replace("/login");
      });
  }, [router]);

  // A route change should never leave the mobile drawer covering the page.
  useEffect(() => setDrawerOpen(false), [path]);

  const logout = useCallback(async () => {
    const token = getToken();
    try {
      if (token) await request<void>("/auth/logout", { method: "POST" }, token);
    } finally {
      clearSession();
      router.replace("/");
    }
  }, [router]);

  if (!user) {
    return (
      <main className="grid min-h-screen place-items-center bg-surface-muted text-sm text-slate-500">
        Loading your workspace…
      </main>
    );
  }

  const isPremium = user.plan === "PREMIUM";
  const nav = NAV.filter((item) => !item.premium || isPremium);

  const sidebar = (
    <div className="flex h-full flex-col px-5 py-6">
      <Link href="/dashboard" className="text-lg font-bold tracking-tight text-slate-900">
        Career<span className="text-brand-600">Pilot</span>
      </Link>
      <p className="mt-1 text-xs text-slate-500">
        {isPremium ? "Application command center" : "Resume & ATS workspace"}
      </p>

      <nav className="mt-8 space-y-1">
        {nav.map((item) => {
          const active = path === item.href || path.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cx(
                "block rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-surface-sunken hover:text-slate-900",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto pt-6">
        {isPremium ? (
          <div className="rounded-card bg-surface-inverse p-4 text-white">
            <Badge tone="brand" className="bg-brand-500/15 text-brand-200 ring-brand-400/20">
              Premium
            </Badge>
            <p className="mt-2.5 text-sm font-semibold">Full career toolkit</p>
            <p className="mt-1 text-xs leading-5 text-slate-400">
              Applications, skill gap, roadmap and what-if are all unlocked.
            </p>
          </div>
        ) : (
          <div className="rounded-card border border-brand-100 bg-brand-50 p-4">
            <p className="text-sm font-semibold text-brand-900">Unlock the full workspace</p>
            <p className="mt-1 text-xs leading-5 text-brand-800/80">
              Track applications, see your skill gap and plan a roadmap for every role.
            </p>
            <LinkButton href="/upgrade" size="sm" className="mt-3 w-full">
              Upgrade
            </LinkButton>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-surface-muted text-slate-900">
      <aside className="fixed inset-y-0 hidden w-64 border-r border-line bg-white lg:block">{sidebar}</aside>

      {drawerOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            aria-label="Close navigation"
            onClick={() => setDrawerOpen(false)}
            className="absolute inset-0 bg-slate-900/40"
          />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-line bg-white shadow-lg">{sidebar}</aside>
        </div>
      ) : null}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-white/90 px-5 backdrop-blur sm:px-8">
          <Button
            variant="ghost"
            size="sm"
            aria-label="Open navigation"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(true)}
            className="lg:hidden"
          >
            <span aria-hidden className="text-base leading-none">
              ☰
            </span>
          </Button>
          <Link href="/dashboard" className="text-base font-bold lg:hidden">
            Career<span className="text-brand-600">Pilot</span>
          </Link>

          <div className="ml-auto flex items-center gap-3">
            {!isPremium ? (
              <LinkButton href="/upgrade" size="sm" variant="secondary" className="hidden sm:inline-flex">
                Upgrade to Premium
              </LinkButton>
            ) : null}
            <span className="hidden text-right sm:block">
              <b className="block text-sm font-medium leading-tight">{user.name}</b>
              <span className="text-xs text-slate-500">{user.plan}</span>
            </span>
            <Button variant="secondary" size="sm" onClick={logout}>
              Sign out
            </Button>
          </div>
        </header>

        {children}
      </div>
    </div>
  );
}
