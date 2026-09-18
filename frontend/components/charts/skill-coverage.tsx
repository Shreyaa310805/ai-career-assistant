/**
 * How this resume covers the job description, as one stacked bar.
 *
 * A stacked bar rather than a donut: the three counts are frequently close,
 * and close values are exactly what a pie makes hard to read. Segments use the
 * validated categorical trio (identity, not status), are separated by a 2px
 * surface gap, and every segment is named with its count in the legend, so the
 * reading never depends on colour.
 */
const BUCKETS = [
  { key: "matched", label: "Matched", color: "var(--viz-series-3)", help: "On your resume and asked for by the role." },
  { key: "missing", label: "Missing", color: "var(--viz-series-2)", help: "Asked for by the role but not evidenced on your resume." },
  { key: "extra", label: "Additional", color: "var(--viz-series-1)", help: "On your resume but not requested by this role." },
] as const;

export function SkillCoverage({
  matched,
  missing,
  extra,
}: {
  matched: number;
  missing: number;
  extra: number;
}) {
  const counts: Record<string, number> = { matched, missing, extra };
  const total = matched + missing + extra;

  if (total === 0) {
    return <p className="text-sm text-slate-500">No skills were detected for this comparison yet.</p>;
  }

  const required = matched + missing;
  const coverage = required > 0 ? Math.round((matched / required) * 100) : 0;

  return (
    <figure className="m-0">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm text-slate-500">Job-description coverage</span>
        <span className="text-sm font-semibold text-slate-900 tabular-nums">
          {matched} of {required} required skills · {coverage}%
        </span>
      </div>

      <div
        className="mt-3 flex h-3 w-full gap-0.5 overflow-hidden rounded-full"
        role="img"
        aria-label={`${matched} matched, ${missing} missing, ${extra} additional skills`}
      >
        {BUCKETS.map((bucket) => {
          const value = counts[bucket.key];
          if (value === 0) return null;
          return (
            <div
              key={bucket.key}
              style={{
                flexGrow: value,
                background: bucket.color,
                transition: "flex-grow 600ms cubic-bezier(0.16, 1, 0.3, 1)",
              }}
            />
          );
        })}
      </div>

      <figcaption className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
        {BUCKETS.map((bucket) => (
          <span key={bucket.key} className="flex items-center gap-2 text-sm" title={bucket.help}>
            <span
              aria-hidden
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ background: bucket.color }}
            />
            <span className="text-slate-600">{bucket.label}</span>
            <span className="font-semibold text-slate-900 tabular-nums">{counts[bucket.key]}</span>
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
