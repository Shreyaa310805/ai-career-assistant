import { Badge, type Tone } from "@/components/ui";
import { ScoreDial } from "@/components/interview-charts";

const RECOMMENDATION_TONE: Record<string, Tone> = {
  strong_hire: "success",
  hire: "success",
  borderline: "warning",
  no_hire: "danger",
};

const RECOMMENDATION_LABEL: Record<string, string> = {
  strong_hire: "Strong hire",
  hire: "Hire",
  borderline: "Borderline",
  no_hire: "Needs more practice",
};

export function SessionSummaryCard({
  summary,
  recommendation,
  averageScore,
  averageConfidence,
}: {
  summary: string;
  recommendation: string;
  averageScore: number | null;
  averageConfidence: number | null;
}) {
  return (
    <section className="rounded-card border border-brand-100 bg-gradient-to-br from-brand-50/70 to-white p-6">
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="flex gap-4">
          <ScoreDial label="Score" value={averageScore} size="lg" />
          <ScoreDial label="Confidence" value={averageConfidence} size="lg" />
        </div>
        <div className="min-w-[220px] flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-slate-900">Overall assessment</p>
            {recommendation ? (
              <Badge tone={RECOMMENDATION_TONE[recommendation] ?? "neutral"}>
                {RECOMMENDATION_LABEL[recommendation] ?? recommendation}
              </Badge>
            ) : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-700">{summary}</p>
        </div>
      </div>
    </section>
  );
}
