/**
 * A bounded 0-100 score is a single headline number, so the gauge exists to
 * frame one hero numeral rather than to be read off an arc. Color bands the
 * reading (status, not identity) and is always paired with a written verdict,
 * so the meaning never rests on hue alone.
 */
const BANDS = [
  { min: 75, label: "Strong", color: "var(--viz-good)", tone: "text-emerald-700" },
  { min: 50, label: "Needs work", color: "var(--viz-warning)", tone: "text-amber-700" },
  { min: 0, label: "At risk", color: "var(--viz-critical)", tone: "text-rose-700" },
] as const;

export function bandFor(score: number) {
  return BANDS.find((band) => score >= band.min) ?? BANDS[BANDS.length - 1];
}

export function ScoreGauge({
  score,
  label,
  caption,
  size = 180,
}: {
  score: number;
  label: string;
  caption?: string;
  size?: number;
}) {
  const value = Math.max(0, Math.min(100, score));
  const band = bandFor(value);

  const stroke = Math.round(size * 0.075);
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  // Three-quarter arc: leaves a visual base so the ring reads as a dial.
  const sweep = 0.75;
  const arc = circumference * sweep;

  return (
    <figure className="m-0 flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={`${label}: ${value} out of 100 — ${band.label}`}
          className="-rotate-[225deg]"
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--viz-track)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${arc} ${circumference}`}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={band.color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${(arc * value) / 100} ${circumference}`}
            style={{ transition: "stroke-dasharray 700ms cubic-bezier(0.16, 1, 0.3, 1)" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[2.75rem] font-bold leading-none tracking-tight text-slate-900 tabular-nums">
            {Math.round(value)}
          </span>
          <span className="mt-0.5 text-xs font-medium text-slate-400">out of 100</span>
          <span className={`mt-2 text-sm font-semibold ${band.tone}`}>{band.label}</span>
        </div>
      </div>
      <figcaption className="mt-3 text-center">
        <span className="block text-sm font-semibold text-slate-900">{label}</span>
        {caption ? <span className="mt-1 block max-w-[22ch] text-xs leading-5 text-slate-500">{caption}</span> : null}
      </figcaption>
    </figure>
  );
}
