"use client";

import { RoadmapGate, useRoadmap } from "@/components/workspace/use-roadmap";
import { Badge, Card, CardHeader, LinkButton, type Tone } from "@/components/ui";
import type { Priority } from "@/lib/career";

const TONE: Record<Priority, Tone> = { High: "danger", Medium: "warning", Low: "success" };

export default function RoadmapPage() {
  const { roadmap, error, loading, applicationId } = useRoadmap();

  if (!roadmap) return <RoadmapGate loading={loading} error={error} applicationId={applicationId} />;

  const steps = roadmap.prioritized_skills;

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-600">Target</p>
        <h2 className="mt-1.5 text-xl font-bold tracking-tight">
          {roadmap.role} at {roadmap.company}
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          You currently match <b className="text-slate-900">{roadmap.current_match_score}%</b> of what this role
          asks for. Working through the steps below in order closes the highest-weighted gaps first.
        </p>
      </Card>

      <Card>
        <CardHeader
          title="Your plan"
          description={`${steps.length} step${steps.length === 1 ? "" : "s"}, ordered by impact on this role.`}
        />
        {steps.length ? (
          <ol className="p-6">
            {steps.map((step, index) => {
              const resources =
                roadmap.recommendations.find((item) => item.skill === step.skill)?.resources ?? [];
              const isLast = index === steps.length - 1;
              return (
                <li key={step.skill} className="relative flex gap-4 pb-6 last:pb-0">
                  {isLast ? null : (
                    <span aria-hidden className="absolute left-[15px] top-9 h-[calc(100%-1.5rem)] w-px bg-line" />
                  )}
                  <span className="z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-50 text-sm font-bold text-brand-700">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <h3 className="font-semibold">{step.skill}</h3>
                      <Badge tone={TONE[step.priority]}>{step.priority}</Badge>
                    </div>
                    <p className="mt-1.5 text-sm text-slate-500">{step.reason}</p>
                    {resources.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {resources.map((resource) => (
                          <a
                            key={resource.url}
                            href={resource.url}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-brand-300 hover:text-brand-700"
                          >
                            {resource.title}
                            <span className="ml-1.5 text-slate-400">{resource.provider}</span>
                          </a>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
        ) : (
          <div className="p-6">
            <p className="text-sm text-slate-500">
              Nothing to plan — your resume already evidences every requirement detected for this role.
            </p>
          </div>
        )}
      </Card>

      <Card className="bg-surface-muted/60 p-6">
        <h2 className="text-[15px] font-semibold">Not sure which step is worth it?</h2>
        <p className="mt-1.5 text-sm text-slate-500">
          The what-if simulator estimates how far each skill would move your match score.
        </p>
        <LinkButton href={`/applications/${applicationId}/what-if`} size="sm" variant="secondary" className="mt-4">
          Open what-if
        </LinkButton>
      </Card>
    </div>
  );
}
