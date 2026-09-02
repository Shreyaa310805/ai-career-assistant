"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Select, Skeleton } from "@/components/ui";
import {
  compareResumes,
  getVersions,
  selectBestVersion,
  type CompareData,
  type ResumeVersionSummary,
} from "@/lib/resumes";

export default function VersionsPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [versions, setVersions] = useState<ResumeVersionSummary[] | null>(null);
  const [comparison, setComparison] = useState<CompareData | null>(null);
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    getVersions(id)
      .then((result) => {
        const list = result.data.versions;
        setVersions(list);
        if (list.length >= 2) {
          setLeft((current) => current || list[list.length - 2].resume_id);
          setRight((current) => current || list[list.length - 1].resume_id);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [id]);

  useEffect(load, [load]);

  async function compare() {
    if (!left || !right || left === right) {
      setError("Choose two different versions to compare.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      setComparison((await compareResumes(left, right)).data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to compare these versions.");
    } finally {
      setBusy(false);
    }
  }

  async function markBest(resumeId: string) {
    if (!id) return;
    setBusy(true);
    try {
      await selectBestVersion(id, resumeId);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update the best version.");
    } finally {
      setBusy(false);
    }
  }

  if (versions === null) return <Skeleton className="h-72" />;

  if (versions.length === 0) {
    return (
      <Card>
        <EmptyState
          title="No resume versions yet"
          description="Every resume you upload on the Resume & ATS tab is kept here as a numbered version."
        />
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Resume versions" description="Every upload for this role, newest last." />
        <ul className="divide-y divide-line">
          {versions.map((version) => (
            <li key={version.resume_id} className="flex flex-wrap items-center justify-between gap-4 px-6 py-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2.5">
                  <b className="text-sm">Version {version.version_number}</b>
                  {version.is_best_version ? <Badge tone="success">Best</Badge> : null}
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  {new Date(version.created_at).toLocaleString()} · {version.parsed_data.skills.length} skills
                  {version.latest_ats_report
                    ? ` · ATS ${Math.round(version.latest_ats_report.ats_score)} · match ${Math.round(version.latest_ats_report.match_score)}`
                    : " · not analysed yet"}
                </p>
              </div>
              {version.is_best_version ? null : (
                <Button variant="secondary" size="sm" disabled={busy} onClick={() => markBest(version.resume_id)}>
                  Mark as best
                </Button>
              )}
            </li>
          ))}
        </ul>
      </Card>

      {versions.length >= 2 ? (
        <Card>
          <CardHeader title="Compare two versions" description="See what changed between uploads." />
          <div className="space-y-5 p-6">
            <div className="flex flex-wrap items-end gap-4">
              <label className="text-sm font-medium">
                <span className="label">Version A</span>
                <Select className="mt-1.5" value={left} onChange={(event) => setLeft(event.target.value)}>
                  {versions.map((version) => (
                    <option key={version.resume_id} value={version.resume_id}>
                      Version {version.version_number}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="text-sm font-medium">
                <span className="label">Version B</span>
                <Select className="mt-1.5" value={right} onChange={(event) => setRight(event.target.value)}>
                  {versions.map((version) => (
                    <option key={version.resume_id} value={version.resume_id}>
                      Version {version.version_number}
                    </option>
                  ))}
                </Select>
              </label>
              <Button onClick={compare} disabled={busy}>
                {busy ? "Comparing…" : "Compare"}
              </Button>
            </div>

            {error ? <Alert>{error}</Alert> : null}

            {comparison ? (
              <div className="rounded-card border border-line bg-surface-muted p-5">
                <p className="text-sm font-semibold">
                  Recommended:{" "}
                  {comparison.recommended_version === "tie"
                    ? "no clear winner"
                    : `Version ${
                        comparison.recommended_version === "v1"
                          ? comparison.resume_v1.version_number
                          : comparison.resume_v2.version_number
                      }`}
                </p>
                <p className="mt-1 text-sm text-slate-600">{comparison.recommendation_reason}</p>

                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <SkillDelta title="Skills gained" skills={comparison.diff.skills_gained} tone="success" />
                  <SkillDelta title="Skills lost" skills={comparison.diff.skills_lost} tone="danger" />
                </div>

                <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 text-sm">
                  <Delta label="ATS score" value={comparison.diff.ats_score_delta} />
                  <Delta label="Match score" value={comparison.diff.match_score_delta} />
                  <Delta label="Experience (years)" value={comparison.diff.experience_years_delta} />
                </dl>
              </div>
            ) : null}
          </div>
        </Card>
      ) : null}
    </div>
  );
}

function SkillDelta({ title, skills, tone }: { title: string; skills: string[]; tone: "success" | "danger" }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h3>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {skills.length ? (
          skills.map((skill) => (
            <Badge key={skill} tone={tone}>
              {skill}
            </Badge>
          ))
        ) : (
          <span className="text-sm text-slate-400">None</span>
        )}
      </div>
    </div>
  );
}

function Delta({ label, value }: { label: string; value: number | null }) {
  if (value === null || value === undefined) return null;
  const sign = value > 0 ? "+" : "";
  const tone = value > 0 ? "text-emerald-700" : value < 0 ? "text-rose-700" : "text-slate-600";
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className={`font-semibold tabular-nums ${tone}`}>
        {sign}
        {value.toFixed(1)}
      </dd>
    </div>
  );
}
