"use client";

import { PriorityBars } from "@/components/charts/priority-bars";
import { SkillCoverage } from "@/components/charts/skill-coverage";
import { RoadmapGate, useRoadmap } from "@/components/workspace/use-roadmap";
import { Badge, Card, CardHeader, type Tone } from "@/components/ui";
import type { Priority } from "@/lib/career";

const GROUPS: { priority: Priority; tone: Tone; blurb: string }[] = [
  { priority: "High", tone: "danger", blurb: "Close these first — they carry the most weight for this role." },
  { priority: "Medium", tone: "warning", blurb: "Worth adding once the high-priority gaps are covered." },
  { priority: "Low", tone: "success", blurb: "Nice to have; least effect on your match score." },
];

export default function SkillGapPage() {
  const { roadmap, error, loading, applicationId } = useRoadmap();

  if (!roadmap) return <RoadmapGate loading={loading} error={error} applicationId={applicationId} />;

  const { skill_gap: gap, prioritized_skills: prioritized } = roadmap;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Role match" value={`${roadmap.current_match_score}%`} />
        <Stat label="Skills to close" value={gap.skill_gap_count} />
        <Stat label="Already matched" value={gap.matched_skills.length} />
      </div>

      <Card className="p-6">
        <h2 className="text-[15px] font-semibold">Coverage</h2>
        <div className="mt-4">
          <SkillCoverage
            matched={gap.matched_skills.length}
            missing={gap.missing_skills.length}
            extra={gap.extra_skills.length}
          />
        </div>
      </Card>

      <Card>
        <CardHeader
          title="What to build, in order"
          description="Ranked by how much each gap affects this role. Hover a row for the reasoning."
        />
        <div className="p-3">
          <PriorityBars skills={prioritized} />
        </div>
      </Card>

      <Card>
        <CardHeader title="Gaps by priority" />
        <div className="grid gap-6 p-6 md:grid-cols-3">
          {GROUPS.map((group) => {
            const skills = prioritized.filter((item) => item.priority === group.priority);
            return (
              <div key={group.priority}>
                <div className="flex items-center gap-2">
                  <Badge tone={group.tone}>{group.priority}</Badge>
                  <span className="text-sm text-slate-500 tabular-nums">{skills.length}</span>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-500">{group.blurb}</p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {skills.length ? (
                    skills.map((item) => (
                      <Badge key={item.skill} tone={group.tone}>
                        {item.skill}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-sm text-slate-400">None</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-[15px] font-semibold">Requirements you meet</h2>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {gap.matched_skills.length ? (
              gap.matched_skills.map((skill) => (
                <Badge key={skill} tone="success">
                  {skill}
                </Badge>
              ))
            ) : (
              <p className="text-sm text-slate-500">None detected yet.</p>
            )}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="text-[15px] font-semibold">Skills beyond this role</h2>
          <p className="mt-1 text-sm text-slate-500">On your resume but not asked for here.</p>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {gap.extra_skills.length ? (
              gap.extra_skills.map((skill) => <Badge key={skill}>{skill}</Badge>)
            ) : (
              <p className="text-sm text-slate-500">None.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums">{value}</p>
    </Card>
  );
}
