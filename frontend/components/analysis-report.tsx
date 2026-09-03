import { ComponentBars, toComponents } from "@/components/charts/component-bars";
import { ScoreGauge } from "@/components/charts/score-gauge";
import { SkillCoverage } from "@/components/charts/skill-coverage";
import { Badge, Card, type Tone } from "@/components/ui";
import type { ImprovementSuggestion } from "@/lib/resumes";

/** The rendered form of one ATS analysis, shared by the free scan and the
 *  per-application workspace so both always show the same thing. */
export type AnalysisView = {
  ats_score: number;
  match_score: number;
  matched_skills: string[];
  missing_skills: string[];
  improvement_suggestions: ImprovementSuggestion[];
  ats_breakdown: Record<string, number> | null;
  extra_skills?: string[];
};

const IMPACT_TONE: Record<ImprovementSuggestion["impact"], Tone> = {
  High: "danger",
  Medium: "warning",
  Low: "neutral",
};

export function AnalysisReport({ analysis }: { analysis: AnalysisView }) {
  const extraCount = analysis.extra_skills?.length ?? 0;

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,340px)_1fr]">
        <Card className="grid place-items-center gap-6 p-6 sm:grid-cols-2 lg:grid-cols-1">
          <ScoreGauge
            score={analysis.ats_score}
            label="ATS score"
            caption="How cleanly an applicant tracking system can read this resume."
            size={168}
          />
          <ScoreGauge
            score={analysis.match_score}
            label="Role match"
            caption="How well your skills and experience fit this job description."
            size={168}
          />
        </Card>

        <div className="space-y-6">
          <Card className="p-6">
            <h3 className="text-[15px] font-semibold">Why this ATS score</h3>
            <p className="mt-1 text-sm text-slate-500">
              Each check contributes a fixed number of points. The lighter track is what is still available.
            </p>
            <div className="mt-5">
              <ComponentBars components={toComponents(analysis.ats_breakdown)} />
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-[15px] font-semibold">Skill coverage</h3>
            <div className="mt-4">
              <SkillCoverage
                matched={analysis.matched_skills.length}
                missing={analysis.missing_skills.length}
                extra={extraCount}
              />
            </div>
          </Card>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="p-6">
          <h3 className="text-[15px] font-semibold">Requirements you already evidence</h3>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {analysis.matched_skills.length ? (
              analysis.matched_skills.map((skill) => (
                <Badge key={skill} tone="success">
                  {skill}
                </Badge>
              ))
            ) : (
              <p className="text-sm text-slate-500">
                None of this role&rsquo;s requirements were found on your resume.
              </p>
            )}
          </div>
        </Card>

        <Card className="p-6">
          <h3 className="text-[15px] font-semibold">Requirements not found</h3>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {analysis.missing_skills.length ? (
              analysis.missing_skills.map((skill) => (
                <Badge key={skill} tone="danger">
                  {skill}
                </Badge>
              ))
            ) : (
              <p className="text-sm text-slate-500">
                Nothing missing — your resume covers every requirement we could detect.
              </p>
            )}
          </div>
        </Card>
      </div>

      <Card>
        <div className="border-b border-line px-6 py-4">
          <h3 className="text-[15px] font-semibold">What to change</h3>
          <p className="mt-1 text-sm text-slate-500">Ordered by how much each change is likely to matter.</p>
        </div>
        <ul className="divide-y divide-line">
          {analysis.improvement_suggestions.map((suggestion, index) => (
            <li key={`${suggestion.category}-${index}`} className="flex gap-4 px-6 py-4">
              <Badge tone={IMPACT_TONE[suggestion.impact]} className="mt-0.5 shrink-0">
                {suggestion.impact}
              </Badge>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  {suggestion.category}
                </p>
                <p className="mt-1 text-sm leading-6 text-slate-700">{suggestion.action}</p>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
