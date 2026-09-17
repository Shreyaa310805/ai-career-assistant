"use client";

import { FormEvent, useEffect, useState } from "react";
import { WhatIfDelta } from "@/components/charts/what-if-delta";
import { RoadmapGate, useRoadmap } from "@/components/workspace/use-roadmap";
import { Alert, Badge, Button, Card, CardHeader, Select, type Tone } from "@/components/ui";
import { simulateWhatIf, type Priority, type WhatIfResult } from "@/lib/career";

const IMPACT_TONE: Record<Priority, Tone> = { High: "success", Medium: "warning", Low: "neutral" };
const PROFICIENCY_LEVELS = [
  { label: "Low", value: 0.33 },
  { label: "Medium", value: 0.66 },
  { label: "High", value: 1 },
] as const;

const LEVEL_TONES: Record<(typeof PROFICIENCY_LEVELS)[number]["label"], Tone> = {
  Low: "warning",
  Medium: "info",
  High: "success",
};

function proficiencyLabel(value: number) {
  return PROFICIENCY_LEVELS.find((level) => level.value === value)?.label ?? "Unknown";
}

export default function WhatIfPage() {
  const { roadmap, error, loading, applicationId } = useRoadmap();
  const missing = roadmap?.skill_gap.missing_skills ?? [];
  const matched = roadmap?.skill_gap.matched_skills ?? [];
  const skills = [
    ...missing.map((name) => ({ name, current: PROFICIENCY_LEVELS[0] })),
    ...matched.map((name) => ({ name, current: PROFICIENCY_LEVELS[1] })),
  ];

  const [skill, setSkill] = useState("");
  const [targetLevel, setTargetLevel] = useState<number>(PROFICIENCY_LEVELS[1].value);
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (skills.length && !skills.some((item) => item.name === skill)) {
      const initial = skills[0];
      setSkill(initial.name);
      setTargetLevel(PROFICIENCY_LEVELS.find((level) => level.value > initial.current.value)?.value ?? initial.current.value);
      setResult(null);
    }
  }, [skills, skill]);

  if (!roadmap) return <RoadmapGate loading={loading} error={error} applicationId={applicationId} />;

  const selectedSkill = skills.find((item) => item.name === skill) ?? skills[0];
  const availableTargets = selectedSkill
    ? PROFICIENCY_LEVELS.filter((level) => level.value > selectedSkill.current.value)
    : [];

  function selectSkill(nextSkill: string) {
    const next = skills.find((item) => item.name === nextSkill);
    if (!next) return;
    setSkill(nextSkill);
    setTargetLevel(PROFICIENCY_LEVELS.find((level) => level.value > next.current.value)?.value ?? next.current.value);
    setResult(null);
    setFormError("");
  }

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

  if (skills.length === 0) {
    return (
      <Card className="p-6">
        <h2 className="text-[15px] font-semibold">No role skills to simulate</h2>
        <p className="mt-1.5 text-sm text-slate-500">
          Run an ATS analysis with a job description that includes skills to explore improvement scenarios.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="What-if simulator"
          description="See the skill evidence found in your resume, then simulate the impact of reaching the next proficiency level."
        />
        <form onSubmit={submit} className="flex flex-wrap items-end gap-5 p-6">
          <label className="min-w-[200px] text-sm font-medium">
            <span className="label">Skill</span>
            <Select className="mt-1.5" value={skill} onChange={(event) => selectSkill(event.target.value)}>
              {skills.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name} — {item.current.label}
                </option>
              ))}
            </Select>
          </label>

          <div className="min-w-[260px]">
            <p className="label">Current resume evidence level</p>
            <Badge className="mt-1.5" tone={selectedSkill ? LEVEL_TONES[selectedSkill.current.label] : "neutral"}>
              {selectedSkill?.current.label}
            </Badge>
            <p className="mt-2 max-w-[300px] text-xs leading-5 text-slate-500">
              {selectedSkill?.current.label === "Low"
                ? "This skill was not evidenced in the resume used for this role."
                : "This skill was evidenced in the resume used for this role."}
            </p>
            <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Explore improvement to</p>
            <div className="mt-1.5 flex gap-2" role="group" aria-label="Target proficiency">
              {PROFICIENCY_LEVELS.map((level) => {
                const isCurrentOrLower = !selectedSkill || level.value <= selectedSkill.current.value;
                return (
                  <Button
                    key={level.label}
                    type="button"
                    size="sm"
                    variant={targetLevel === level.value ? "primary" : "secondary"}
                    disabled={isCurrentOrLower}
                    aria-pressed={targetLevel === level.value}
                    onClick={() => setTargetLevel(level.value)}
                  >
                    {isCurrentOrLower && level.value === selectedSkill?.current.value ? `${level.label} (current)` : level.label}
                  </Button>
                );
              })}
            </div>
          </div>

          <Button type="submit" disabled={busy || availableTargets.length === 0}>
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
            <p className="mb-4 text-sm text-slate-600">
              <span className="font-semibold text-slate-900">{proficiencyLabel(result.current_level)}</span>
              <span aria-hidden="true"> → </span>
              <span className="sr-only"> to </span>
              <span className="font-semibold text-slate-900">{proficiencyLabel(result.target_level)}</span> evidence level
            </p>
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
