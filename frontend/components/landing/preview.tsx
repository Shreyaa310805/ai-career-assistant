import { ComponentBars, toComponents } from "@/components/charts/component-bars";
import { ScoreGauge } from "@/components/charts/score-gauge";
import { SkillCoverage } from "@/components/charts/skill-coverage";
import { Badge } from "@/components/ui";

/**
 * A still of the real product, built from the real chart components against
 * illustrative figures. Labelled as an example so it is never mistaken for
 * the viewer's own result.
 */
const SAMPLE_BREAKDOWN = {
  contact_completeness: 15,
  section_coverage: 20,
  skills_listed: 15,
  quantified_impact: 12,
  length_check: 15,
  work_history_structure: 15,
};

const MATCHED = ["Python", "FastAPI", "PostgreSQL", "Docker", "REST"];
const MISSING = ["Kubernetes", "Terraform", "Kafka"];

export function AppPreview() {
  return (
    <div className="rounded-2xl border border-line bg-white p-2 shadow-lg">
      <div className="flex items-center gap-1.5 px-3 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-rose-300" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-300" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-300" />
        <span className="ml-3 text-xs text-slate-400">Example analysis · Senior Backend Engineer</span>
      </div>

      <div className="rounded-xl bg-surface-muted p-4 sm:p-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,220px)_1fr]">
          <div className="rounded-card border border-line bg-white p-5">
            <ScoreGauge score={82} label="ATS score" size={156} />
          </div>

          <div className="space-y-4">
            <div className="rounded-card border border-line bg-white p-5">
              <h3 className="text-sm font-semibold text-slate-900">Why this score</h3>
              <div className="mt-4">
                <ComponentBars components={toComponents(SAMPLE_BREAKDOWN)} />
              </div>
            </div>

            <div className="rounded-card border border-line bg-white p-5">
              <h3 className="text-sm font-semibold text-slate-900">Skill coverage</h3>
              <div className="mt-4">
                <SkillCoverage matched={MATCHED.length} missing={MISSING.length} extra={4} />
              </div>
              <div className="mt-4 flex flex-wrap gap-1.5">
                {MATCHED.slice(0, 4).map((skill) => (
                  <Badge key={skill} tone="success">
                    {skill}
                  </Badge>
                ))}
                {MISSING.map((skill) => (
                  <Badge key={skill} tone="danger">
                    {skill}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
