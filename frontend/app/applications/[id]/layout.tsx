"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { Alert, Skeleton, cx } from "@/components/ui";
import { getApplication, type Application } from "@/lib/applications";

type Tab = { segment: string; label: string; soon?: boolean };

const TABS: Tab[] = [
  { segment: "", label: "Overview" },
  { segment: "ats", label: "Resume & ATS" },
  { segment: "versions", label: "Resume versions" },
  { segment: "skill-gap", label: "Skill gap" },
  { segment: "roadmap", label: "Roadmap" },
  { segment: "what-if", label: "What-if" },
  { segment: "learning", label: "Learning" },
  { segment: "interview", label: "Interview", soon: true },
];

/**
 * The per-application workspace frame: the role header and the secondary
 * navigation stay mounted while the tool pages below them change.
 */
export default function ApplicationLayout({ children }: { children: ReactNode }) {
  const params = useParams<{ id: string }>();
  const path = usePathname();
  const id = params?.id;
  const [app, setApp] = useState<Application | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) {
      setError("This application link is missing an ID.");
      return;
    }
    getApplication(id)
      .then(setApp)
      .catch((requestError: Error) => setError(requestError.message));
  }, [id]);

  if (error) {
    return (
      <AppShell>
        <main className="mx-auto max-w-3xl px-5 py-8 sm:px-8">
          <Alert>{error}</Alert>
          <Link href="/applications" className="mt-4 inline-block text-sm font-medium text-brand-600">
            ← Back to applications
          </Link>
        </main>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
        <Link href="/applications" className="text-sm font-medium text-brand-600 hover:text-brand-700">
          ← All applications
        </Link>

        {app ? (
          <header className="mt-4 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{app.role}</h1>
              <p className="mt-1.5 text-slate-500">
                {app.company}
                {app.location ? ` · ${app.location}` : ""}
                {app.applied_at ? ` · applied ${new Date(app.applied_at).toLocaleDateString()}` : ""}
              </p>
            </div>
            <StatusBadge status={app.status} />
          </header>
        ) : (
          <Skeleton className="mt-4 h-16 w-full max-w-md" />
        )}

        <div className="mt-8 grid gap-8 lg:grid-cols-[196px_1fr]">
          <nav aria-label="Workspace sections" className="lg:sticky lg:top-24 lg:self-start">
            <ul className="flex gap-1 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
              {TABS.map((tab) => {
                const href = `/applications/${id}${tab.segment ? `/${tab.segment}` : ""}`;
                const active = path === href;
                return (
                  <li key={tab.label} className="shrink-0">
                    <Link
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={cx(
                        "flex items-center justify-between gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors lg:whitespace-normal",
                        active
                          ? "bg-brand-50 text-brand-700"
                          : "text-slate-600 hover:bg-surface-sunken hover:text-slate-900",
                      )}
                    >
                      {tab.label}
                      {tab.soon ? (
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-500">
                          Soon
                        </span>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="min-w-0">{children}</div>
        </div>
      </main>
    </AppShell>
  );
}
