"use client";

import { RoadmapGate, useRoadmap } from "@/components/workspace/use-roadmap";
import { Badge, Card, CardHeader, type Tone } from "@/components/ui";
import type { Priority } from "@/lib/career";

const TONE: Record<Priority, Tone> = { High: "danger", Medium: "warning", Low: "success" };

const TYPE_LABEL: Record<string, string> = {
  documentation: "Docs",
  tutorial: "Tutorial",
  course: "Course",
  practice: "Practice",
  project: "Project",
};

export default function LearningPage() {
  const { roadmap, error, loading, applicationId } = useRoadmap();

  if (!roadmap) return <RoadmapGate loading={loading} error={error} applicationId={applicationId} />;

  const recommendations = roadmap.recommendations;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Learning resources"
          description="A starting point for each gap, grouped by skill and ordered by priority."
        />
        {recommendations.length ? (
          <div className="divide-y divide-line">
            {recommendations.map((recommendation) => (
              <section key={recommendation.skill} className="px-6 py-5">
                <div className="flex flex-wrap items-center gap-2.5">
                  <h3 className="font-semibold">{recommendation.skill}</h3>
                  <Badge tone={TONE[recommendation.priority]}>{recommendation.priority}</Badge>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {recommendation.resources.map((resource) => (
                    <a
                      key={resource.url}
                      href={resource.url}
                      target="_blank"
                      rel="noreferrer"
                      className="group rounded-card border border-line p-4 transition-colors hover:border-brand-300 hover:bg-brand-50/40"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p className="font-medium text-slate-900 group-hover:text-brand-700">{resource.title}</p>
                        <span aria-hidden className="text-slate-300 group-hover:text-brand-500">
                          ↗
                        </span>
                      </div>
                      <p className="mt-1.5 text-sm text-slate-500">{resource.provider}</p>
                      <div className="mt-3 flex gap-1.5">
                        <Badge>{TYPE_LABEL[resource.type] ?? resource.type}</Badge>
                        <Badge>{resource.difficulty}</Badge>
                      </div>
                    </a>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <div className="p-6">
            <p className="text-sm text-slate-500">
              No gaps to study — your resume already covers this role&rsquo;s detected requirements.
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
