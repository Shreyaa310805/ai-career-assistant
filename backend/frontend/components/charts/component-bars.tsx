/**
 * Earned vs available points for each named ATS sub-component.
 *
 * One measure across nominal categories, so: horizontal bars, a single series
 * colour for every bar (never a value-ramp), a recessive track showing the
 * points still on the table, and a direct label on each row.
 */
export type ScoreComponent = { key: string; label: string; earned: number; available: number };

// Maximum points each sub-component can contribute, from ats_engine.py.
export const ATS_COMPONENT_MAX: Record<string, { label: string; max: number; hint: string }> = {
  jd_keyword_coverage: { label: "JD keyword coverage", max: 45, hint: "How much of this job description's skill vocabulary your resume covers." },
  contact_completeness: { label: "Contact details", max: 10, hint: "An email address and a phone number near the top." },
  section_coverage: { label: "Section coverage", max: 15, hint: "Clearly labelled Experience, Education and Skills headings." },
  quantified_impact: { label: "Quantified impact", max: 15, hint: "Bullets that carry numbers, percentages or scale." },
  length_check: { label: "Length", max: 10, hint: "Roughly 250–1100 words parses cleanly; far outside that is penalised." },
  work_history_structure: { label: "Work history", max: 5, hint: "Structured roles with company, dates and bullets." },
};

export function toComponents(breakdown: Record<string, number> | null | undefined): ScoreComponent[] {
  if (!breakdown) return [];
  return Object.entries(ATS_COMPONENT_MAX)
    .filter(([key]) => key in breakdown)
    .map(([key, meta]) => ({
      key,
      label: meta.label,
      earned: breakdown[key],
      available: meta.max,
    }));
}

export function ComponentBars({ components }: { components: ScoreComponent[] }) {
  if (components.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Run an analysis to see how each part of your resume contributed to the score.
      </p>
    );
  }

  return (
    <ul className="space-y-3.5">
      {components.map((component) => {
        const pct = component.available > 0 ? (component.earned / component.available) * 100 : 0;
        const hint = ATS_COMPONENT_MAX[component.key]?.hint;
        return (
          <li key={component.key}>
            <div className="flex items-baseline justify-between gap-4">
              <span className="text-sm font-medium text-slate-700" title={hint}>
                {component.label}
              </span>
              <span className="text-sm text-slate-500 tabular-nums">
                <span className="font-semibold text-slate-900">{Math.round(component.earned)}</span>
                {" / "}
                {component.available}
              </span>
            </div>
            <div
              className="mt-1.5 h-2 w-full overflow-hidden rounded-full"
              style={{ background: "var(--viz-track)" }}
              role="img"
              aria-label={`${component.label}: ${Math.round(component.earned)} of ${component.available} points`}
            >
              <div
                className="h-full rounded-full"
                style={{
                  width: `${Math.max(pct, 0)}%`,
                  background: "var(--viz-series-1)",
                  transition: "width 600ms cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
