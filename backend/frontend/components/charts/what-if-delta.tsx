/**
 * Current vs projected match score for one skill.
 *
 * Both bars measure the same thing on the same 0-100 axis, so they share one
 * scale; the projected bar is tinted and labelled rather than plotted against
 * a second axis.
 */
export function WhatIfDelta({
  current,
  projected,
  gain,
}: {
  current: number;
  projected: number;
  gain: number;
}) {
  const rows = [
    { label: "Today", value: current, color: "var(--viz-track)", text: "text-slate-700" },
    { label: "Projected", value: projected, color: "var(--viz-series-1)", text: "text-slate-900" },
  ];

  return (
    <figure className="m-0">
      <div className="space-y-3">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="flex items-baseline justify-between gap-4">
              <span className="text-sm text-slate-600">{row.label}</span>
              <span className={`text-sm font-semibold tabular-nums ${row.text}`}>{row.value.toFixed(1)}%</span>
            </div>
            <div className="mt-1.5 h-2.5 w-full overflow-hidden rounded-full bg-surface-sunken">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${Math.max(0, Math.min(100, row.value))}%`,
                  background: row.color,
                  transition: "width 600ms cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <figcaption className="mt-4 text-sm text-slate-600">
        Estimated gain{" "}
        <span className="font-semibold text-slate-900 tabular-nums">+{gain.toFixed(1)} points</span>
      </figcaption>
    </figure>
  );
}
