"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AnalysisReport, type AnalysisView } from "@/components/analysis-report";
import { AppShell } from "@/components/app-shell";
import { ScanPanel } from "@/components/scan-panel";
import { StatusBadge } from "@/components/status-badge";
import { Badge, Card, EmptyState, LinkButton, SectionHeading, Skeleton } from "@/components/ui";
import { getCurrentUser, type User } from "@/lib/auth";
import { getSummary, type Summary } from "@/lib/applications";
import { analyzeQuickScan, getLatestQuickScan, uploadQuickResume } from "@/lib/quick-scan";
import type { AnalyzeData } from "@/lib/resumes";

export default function Dashboard() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    getCurrentUser().then(setUser).catch(() => setUser(null));
  }, []);

  if (!user) {
    return (
      <AppShell>
        <main className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
          <Skeleton className="h-9 w-72" />
          <Skeleton className="mt-6 h-64 w-full" />
        </main>
      </AppShell>
    );
  }

  return <AppShell>{user.plan === "PREMIUM" ? <PremiumDashboard /> : <FreeDashboard />}</AppShell>;
}

/* -------------------------------------------------------------------------- */
/* FREE — the scanning surface is the product                                 */
/* -------------------------------------------------------------------------- */

const LOCKED = [
  { title: "Application tracker", body: "Track every company, role, date and status in one pipeline." },
  { title: "Skill gap & roadmap", body: "Ranked gaps and a sequenced plan for each role you are chasing." },
  { title: "Resume versions", body: "Compare tailored versions and keep the strongest one per application." },
];

function FreeDashboard() {
  const [analysis, setAnalysis] = useState<AnalysisView | null>(null);
  const [loading, setLoading] = useState(true);
  const [resume, setResume] = useState<{ resume_id: string; version_number: number; skills: string[] } | null>(null);

  useEffect(() => {
    getLatestQuickScan()
      .then((result) => {
        const { resume: latestResume, report } = result.data;
        if (latestResume) {
          setResume({
            resume_id: latestResume.resume_id,
            version_number: latestResume.version_number,
            skills: latestResume.parsed_data.skills,
          });
        }
        if (report) {
          setAnalysis({
            ats_score: report.ats_score,
            match_score: report.match_score,
            matched_skills: report.matched_skills,
            missing_skills: report.missing_skills,
            improvement_suggestions: report.improvement_suggestions,
            ats_breakdown: report.ats_breakdown,
          });
        }
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, []);

  function onAnalyzed(data: AnalyzeData) {
    setAnalysis(data);
    // Bring the freshly rendered result into view rather than leaving the
    // reader at the top of the form.
    requestAnimationFrame(() => document.getElementById("result")?.scrollIntoView({ behavior: "smooth" }));
  }

  return (
    <main className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
      <SectionHeading
        eyebrow="Free plan"
        title="Score your resume against a role"
        description="Upload your resume and the job description. Everything below is computed from the two documents you provide."
      />

      <div className="mt-8">
        {loading ? (
          <div className="grid gap-6 md:grid-cols-2">
            <Skeleton className="h-72" />
            <Skeleton className="h-72" />
          </div>
        ) : (
          <ScanPanel
            upload={uploadQuickResume}
            analyze={analyzeQuickScan}
            initialResume={resume}
            onAnalyzed={onAnalyzed}
          />
        )}
      </div>

      {analysis ? (
        <section id="result" className="mt-10 scroll-mt-24">
          <h2 className="text-xl font-bold tracking-tight">Your results</h2>
          <div className="mt-5">
            <AnalysisReport analysis={analysis} />
          </div>
        </section>
      ) : null}

      <section className="mt-12">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold tracking-tight">Available on Premium</h2>
            <p className="mt-1 text-sm text-slate-500">Built and working — just not included in the free plan.</p>
          </div>
          <LinkButton href="/upgrade" size="sm">Upgrade</LinkButton>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          {LOCKED.map((item) => (
            <Card key={item.title} className="bg-surface-muted/60 p-6">
              <Badge>Premium</Badge>
              <h3 className="mt-3 font-semibold text-slate-700">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-500">{item.body}</p>
            </Card>
          ))}
        </div>
      </section>
    </main>
  );
}

/* -------------------------------------------------------------------------- */
/* PREMIUM — the pipeline overview                                            */
/* -------------------------------------------------------------------------- */

function PremiumDashboard() {
  const [data, setData] = useState<Summary | null>(null);

  useEffect(() => {
    getSummary().then(setData).catch(() => setData(null));
  }, []);

  const metrics: [string, number][] = data
    ? [
        ["Total roles", data.total],
        ["Applied", data.applied],
        ["Interviewing", data.interviewing],
        ["Offers", data.offer],
      ]
    : [];

  const distribution: [string, number][] = data
    ? [
        ["Saved", data.saved],
        ["Applied", data.applied],
        ["Interviewing", data.interviewing],
        ["Selected", data.selected],
        ["Offer", data.offer],
        ["Rejected", data.rejected],
      ].filter(([, value]) => (value as number) > 0) as [string, number][]
    : [];

  const maxCount = Math.max(1, ...distribution.map(([, value]) => value));

  return (
    <main className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
      <SectionHeading
        eyebrow="Overview"
        title="Keep your search moving"
        description="Every opportunity you are tracking, in one view."
        action={<LinkButton href="/applications/new">+ Add application</LinkButton>}
      />

      <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {data
          ? metrics.map(([name, value]) => (
              <Card key={name} className="p-5">
                <p className="text-sm text-slate-500">{name}</p>
                <p className="mt-2 text-3xl font-bold tabular-nums">{value}</p>
              </Card>
            ))
          : Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-[104px]" />)}
      </section>

      <section className="mt-6 grid gap-6 xl:grid-cols-[1.55fr_1fr]">
        <Card>
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <h2 className="text-[15px] font-semibold">Recent applications</h2>
            <Link className="text-sm font-medium text-brand-600 hover:text-brand-700" href="/applications">
              View all
            </Link>
          </div>
          {data?.recent_applications.length ? (
            <ul className="divide-y divide-line">
              {data.recent_applications.map((app) => (
                <li key={app.id}>
                  <Link
                    href={`/applications/${app.id}`}
                    className="flex items-center justify-between gap-4 px-5 py-4 hover:bg-surface-muted"
                  >
                    <span className="min-w-0">
                      <b className="block truncate text-sm">{app.role}</b>
                      <span className="text-sm text-slate-500">
                        {app.company}
                        {app.location ? ` · ${app.location}` : ""}
                      </span>
                    </span>
                    <StatusBadge status={app.status} />
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No applications yet"
              description="Add your first role to start tracking it and unlock its workspace."
              action={<LinkButton href="/applications/new">Add an application</LinkButton>}
            />
          )}
        </Card>

        <Card className="p-6">
          <h2 className="text-[15px] font-semibold">Pipeline by stage</h2>
          {distribution.length ? (
            <ul className="mt-5 space-y-3.5">
              {distribution.map(([label, value]) => (
                <li key={label}>
                  <div className="flex items-baseline justify-between">
                    <span className="text-sm text-slate-600">{label}</span>
                    <span className="text-sm font-semibold tabular-nums">{value}</span>
                  </div>
                  <div
                    className="mt-1.5 h-2 overflow-hidden rounded-full"
                    style={{ background: "var(--viz-track)" }}
                    role="img"
                    aria-label={`${label}: ${value}`}
                  >
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${(value / maxCount) * 100}%`, background: "var(--viz-series-1)" }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-sm text-slate-500">Stages appear here once you add an application.</p>
          )}
        </Card>
      </section>
    </main>
  );
}
