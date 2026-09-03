"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { Card, EmptyState, LinkButton, SectionHeading, Skeleton } from "@/components/ui";
import { getApplications, type Application } from "@/lib/applications";
import { isPlanError } from "@/lib/auth";

const TOOLS = [
  { segment: "skill-gap", label: "Skill gap" },
  { segment: "roadmap", label: "Roadmap" },
  { segment: "what-if", label: "What-if" },
  { segment: "learning", label: "Learning" },
];

/**
 * Career intelligence is always scoped to one application, because it is
 * derived from that application's resume and ATS report. This page is the
 * entry point: pick a role, then jump straight to the tool you want.
 */
export default function CareerPage() {
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
          eyebrow="Career intelligence"
          title="Plan around a specific role"
          description="Skill gap, roadmap, what-if and learning are all derived from one application's resume and ATS analysis."
        />

        <div className="mt-8">
          {locked ? (
            <Card>
              <EmptyState
                title="Career intelligence is a Premium feature"
                description="Upgrade to see ranked skill gaps, a sequenced roadmap and score simulation for every role you track."
                action={<LinkButton href="/upgrade">Upgrade to Premium</LinkButton>}
              />
            </Card>
          ) : apps === null ? (
            <Skeleton className="h-64" />
          ) : apps.length ? (
            <div className="grid gap-4 md:grid-cols-2">
              {apps.map((app) => (
                <Card key={app.id} className="p-6">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        href={`/applications/${app.id}`}
                        className="block truncate font-semibold hover:text-brand-700"
                      >
                        {app.role}
                      </Link>
                      <p className="mt-0.5 text-sm text-slate-500">{app.company}</p>
                    </div>
                    <StatusBadge status={app.status} />
                  </div>

                  <div className="mt-5 flex flex-wrap gap-2">
                    {TOOLS.map((tool) => (
                      <Link
                        key={tool.segment}
                        href={`/applications/${app.id}/${tool.segment}`}
                        className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-brand-300 hover:text-brand-700"
                      >
                        {tool.label}
                      </Link>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <Card>
              <EmptyState
                title="Add an application first"
                description="Career intelligence needs a role to analyse against. Create one, upload a resume, then run an ATS analysis."
                action={<LinkButton href="/applications/new">Add an application</LinkButton>}
              />
            </Card>
          )}
        </div>
      </main>
    </AppShell>
  );
}
