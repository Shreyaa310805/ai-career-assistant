"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { Card, EmptyState, LinkButton, SectionHeading, Skeleton } from "@/components/ui";
import { getApplications, type Application } from "@/lib/applications";
import { isPlanError } from "@/lib/auth";

export default function ApplicationsPage() {
  const [apps, setApps] = useState<Application[] | null>(null);
  const [locked, setLocked] = useState(false);

  useEffect(() => {
    getApplications()
      .then(setApps)
      .catch((error) => {
        if (isPlanError(error)) setLocked(true);
        setApps([]);
      });
  }, []);

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
        <SectionHeading
          eyebrow="Applications"
          title="Your opportunity pipeline"
          description="Each application gets its own workspace for resume, ATS, skills and planning."
          action={locked ? undefined : <LinkButton href="/applications/new">+ Add application</LinkButton>}
        />

        <div className="mt-8">
          {locked ? (
            <Card>
              <EmptyState
                title="The application tracker is a Premium feature"
                description="Upgrade to track companies, roles, dates and status, and to open a dedicated workspace for each role."
                action={<LinkButton href="/upgrade">Upgrade to Premium</LinkButton>}
              />
            </Card>
          ) : apps === null ? (
            <Skeleton className="h-64" />
          ) : apps.length ? (
            <Card className="overflow-hidden">
              <ul className="divide-y divide-line">
                {apps.map((app) => (
                  <li key={app.id}>
                    <Link
                      href={`/applications/${app.id}`}
                      className="grid gap-3 px-5 py-4 transition-colors hover:bg-surface-muted sm:grid-cols-[1.6fr_1fr_auto] sm:items-center"
                    >
                      <span className="min-w-0">
                        <b className="block truncate">{app.role}</b>
                        <span className="text-sm text-slate-500">{app.company}</span>
                      </span>
                      <span className="text-sm text-slate-500">{app.location || "Location not set"}</span>
                      <StatusBadge status={app.status} className="w-fit" />
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          ) : (
            <Card>
              <EmptyState
                title="Build your pipeline"
                description="Track roles here, then open each workspace for role-specific preparation."
                action={<LinkButton href="/applications/new">Add your first application</LinkButton>}
              />
            </Card>
          )}
        </div>
      </main>
    </AppShell>
  );
}
