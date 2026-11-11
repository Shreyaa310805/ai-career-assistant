import type { Tone } from "@/components/ui";

export function scoreTone(value: number): Tone {
  if (value >= 75) return "success";
  if (value >= 45) return "warning";
  return "danger";
}

const DIAL_TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700",
  brand: "bg-brand-50 text-brand-700",
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-800",
  danger: "bg-rose-50 text-rose-700",
  info: "bg-sky-50 text-sky-700",
};

/** A hero-number "dial" for a single 0-100 metric, colored by status. */
export function ScoreDial({
  label,
  value,
  size = "md",
}: {
  label: string;
  value: number | null;
  size?: "sm" | "md" | "lg";
}) {
  const tone = value === null ? "neutral" : scoreTone(value);
  const dims = size === "lg" ? "h-28 w-28" : size === "sm" ? "h-16 w-16" : "h-20 w-20";
  const textSize = size === "lg" ? "text-3xl" : size === "sm" ? "text-base" : "text-xl";
  return (
    <div className={`flex ${dims} shrink-0 flex-col items-center justify-center rounded-full ${DIAL_TONE_CLASSES[tone]}`}>
      <span className={`${textSize} font-bold leading-none`}>{value === null ? "—" : Math.round(value)}</span>
      <span className="mt-1 text-[10px] font-medium uppercase tracking-wide">{label}</span>
    </div>
  );
}

/** A labeled horizontal meter for one 0-100 magnitude value. Single-hue by design. */
export function MetricBar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-slate-600">{label}</span>
        <span className="font-semibold text-slate-900">{Math.round(pct)}</span>
      </div>
      <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-surface-sunken">
        <div className="h-full rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export type TrendPoint = { label: string; value: number | null };

const TREND_CHART_HEIGHT = 128; // px — a fixed plotting area, so bar heights are computed in px, not (browser-unreliable) nested percentages.

/** A small bar chart of one series (overall score) across ordered questions. */
export function ScoreTrendChart({ points }: { points: TrendPoint[] }) {
  const guides = [0, 50, 100];
  return (
    <div className="pl-8">
      <div className="relative" style={{ height: TREND_CHART_HEIGHT }}>
        {guides.map((guide) => (
          <div
            key={guide}
            className="absolute left-0 right-0 border-t border-dashed border-line"
            style={{ bottom: (guide / 100) * TREND_CHART_HEIGHT }}
          >
            <span className="absolute -left-8 -top-2 w-6 text-right text-[10px] text-slate-400">{guide}</span>
          </div>
        ))}
        <div className="absolute inset-0 flex items-end justify-between gap-3">
          {points.map((point, index) => {
            const barHeight = point.value === null ? 0 : Math.max((point.value / 100) * TREND_CHART_HEIGHT, 4);
            return (
              <div
                key={index}
                className="relative flex h-full flex-1 flex-col items-center justify-end"
                title={`${point.label}: ${point.value ?? "not answered"}`}
              >
                <span
                  className="absolute text-xs font-semibold text-slate-700"
                  style={{ bottom: barHeight + 6 }}
                >
                  {point.value ?? "—"}
                </span>
                <div
                  className={`w-full max-w-8 rounded-t-md ${point.value === null ? "bg-surface-sunken" : "bg-brand-600"}`}
                  style={{ height: barHeight }}
                />
              </div>
            );
          })}
        </div>
      </div>
      <div className="mt-2 flex justify-between gap-3">
        {points.map((point, index) => (
          <span key={index} className="flex-1 text-center text-[11px] text-slate-500">
            {point.label}
          </span>
        ))}
      </div>
    </div>
  );
}
