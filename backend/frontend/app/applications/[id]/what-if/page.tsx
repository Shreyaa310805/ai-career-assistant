"use client";

import { FormEvent, useEffect, useState } from "react";
import { WhatIfDelta } from "@/components/charts/what-if-delta";
import { RoadmapGate, useRoadmap } from "@/components/workspace/use-roadmap";
import { Alert, Badge, Button, Card, CardHeader, Select, type Tone } from "@/components/ui";
import { simulateWhatIf, type Priority, type WhatIfResult } from "@/lib/career";

const IMPACT_TONE: Record<Priority, Tone> = { High: "success", Medium: "warning", Low: "neutral" };

export default function WhatIfPage() {
  const { roadmap, error, loading, applicationId } = useRoadmap();
  const missing = roadmap?.skill_gap.missing_skills ?? [];

  const [skill, setSkill] = useState("");
  const [targetLevel, setTargetLevel] = useState(0.75);
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (missing.length && !missing.includes(skill)) {
      setSkill(missing[0]);
      setResult(null);
    }
  }, [missing, skill]);

  if (!roadmap) return <RoadmapGate loading={loading} error={error} applicationId={applicationId} />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!applicationId || !skill) return;
    setBusy(true);
    setFormError("");
    try {
      setResult(await simulateWhatIf(applicationId, skill, targetLevel));
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Unable to estimate the improvement.");
    } finally {
      setBusy(false);
    }
  }

  if (missing.length === 0) {
    return (
      <Card className="p-6">
        <h2 className="text-[15px] font-semibold">Nothing left to simulate</h2>
        <p className="mt-1.5 text-sm text-slate-500">
          Your resume already evidences every requirement detected for this role, so there is no gap to model.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="What-if simulator"
          description="Estimate how far building one missing skill would move your match score for this role."
        />
        <form onSubmit={submit} className="flex flex-wrap items-end gap-5 p-6">
          <label className="min-w-[200px] text-sm font-medium">
            <span className="label">Skill to build</span>
            <Select className="mt-1.5" value={skill} onChange={(event) => setSkill(event.target.value)}>
              {missing.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          </label>

          <label className="min-w-[220px] text-sm font-medium">
            <span className="label">
              Target proficiency: <span className="tabular-nums">{Math.round(targetLevel * 100)}%</span>
            </span>
            <input
              className="mt-4 block w-full accent-brand-600"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={targetLevel}
              onChange={(event) => setTargetLevel(Number(event.target.value))}
            />
          </label>

          <Button type="submit" disabled={busy}>
            {busy ? "Estimating…" : "Estimate impact"}
          </Button>
        </form>
      </Card>

      {formError ? <Alert>{formError}</Alert> : null}

      {result ? (
        <Card>
          <CardHeader
            title={`Learning ${result.skill}`}
            action={<Badge tone={IMPACT_TONE[result.impact]}>{result.impact} impact</Badge>}
          />
          <div className="p-6">
            <WhatIfDelta
              current={result.current_match_score}
              projected={result.estimated_match_score}
              gain={result.estimated_improvement}
            />
            <p className="mt-5 text-sm leading-6 text-slate-600">{result.message}</p>
            <p className="mt-3 text-xs text-slate-400">
              An estimate derived from this role&rsquo;s requirement ordering, not a guarantee.
            </p>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
