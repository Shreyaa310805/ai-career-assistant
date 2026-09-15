"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, Button, Card, CardHeader, LinkButton } from "@/components/ui";
import { downloadInterviewReport, getApplicationInterviewReport, type ApplicationInterviewReport } from "@/lib/interview-reports";

const label = (key: string) => key.replace(/_score$/, "").replaceAll("_", " ");
const score = (value: number | null) => value === null ? "Not assessed" : `${value.toFixed(1)} / 100`;

export default function ApplicationReportPage() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<ApplicationInterviewReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setReport(null);
    getApplicationInterviewReport(id).then(r => { if (active) setReport(r.data); }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id, reload]);
  async function download() {
    setDownloading(true); setError("");
    try { await downloadInterviewReport(id); } catch (e) { setError(e instanceof Error ? e.message : "Download failed"); } finally { setDownloading(false); }
  }
  return <div className="space-y-6">
    <Card><CardHeader title="Application interview report" description="Evidence from completed interview sessions" action={<LinkButton href={`/applications/${id}/interview`} variant="secondary">Practice again</LinkButton>} />
      <div className="space-y-4 p-6">
        {loading && <p role="status">Loading report…</p>}
        {error && <Alert>{error} <Button onClick={() => setReload(r => r + 1)}>Retry</Button></Alert>}
        {!loading && report && <><h2 className="text-2xl font-semibold">{report.company} · {report.role}</h2>
          <p className="text-slate-500">{report.completed_session_count} sessions · {report.total_questions_attempted} attempted · {report.total_questions_evaluated} evaluated</p>
          <p className="text-xl font-semibold text-brand-700">{report.readiness} · {score(report.metrics.overall_score)}</p>
          {report.date_range.from && <p className="text-sm text-slate-500">{new Date(report.date_range.from).toLocaleDateString()} – {new Date(report.date_range.to!).toLocaleDateString()}</p>}
          <Button onClick={download} disabled={downloading}>{downloading ? "Preparing PDF…" : "Download PDF"}</Button>
        </>}
      </div>
    </Card>
    {!loading && report && (report.completed_session_count === 0 ? <Alert tone="info">Complete an interview to see your performance and skill evidence.</Alert> : <>
      <Card className="p-6"><h2 className="font-semibold">Aggregate performance</h2><div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(report.metrics).map(([key, value]) => <div key={key}><div className="flex justify-between gap-2 text-sm"><span className="capitalize">{label(key)}</span><span>{score(value)}</span></div>{value !== null && <div role="meter" aria-label={label(key)} aria-valuenow={value} aria-valuemin={0} aria-valuemax={100} className="mt-2 h-2 rounded-full bg-slate-100"><div style={{ width: `${value}%` }} className="h-2 rounded-full bg-brand-500" /></div>}</div>)}
      </div><div className="mt-6 grid gap-4 sm:grid-cols-2">{(["verbal_confidence", "visual_confidence"] as const).map(key => <div key={key} className="rounded-lg bg-surface-muted p-4"><h3 className="font-medium capitalize">{label(key)}</h3><p>{score(report[key].score)} · {report[key].observations_count} observations</p><p className="mt-2 text-xs text-slate-500">{report[key].basis}</p></div>)}</div><p className="mt-4 text-xs text-slate-500">Answer confidence describes language, not verified acoustic confidence. Visual composure is separate and never changes answer scores.</p></Card>
      <Card className="p-6"><h2 className="font-semibold">Session performance</h2><div className="mt-4 grid gap-4 sm:grid-cols-2">{report.sessions.map(s => <div key={s.interview_id} className="rounded-lg border border-line p-4"><LinkButton href={`/applications/${id}/interview/${s.interview_id}`} variant="secondary">{s.personality} · {s.difficulty} · {s.mode}</LinkButton><p className="mt-3">{score(s.overall_score)} · {s.questions_attempted} attempted</p><p className="text-xs text-slate-500">{s.completed_at && new Date(s.completed_at).toLocaleString()}</p><p className="mt-3 text-sm">Strengths: {s.strengths.join("; ") || "No recorded observations"}</p><p className="mt-2 text-sm">Improve: {s.areas_to_improve.join("; ") || "No recorded observations"}</p></div>)}</div></Card>
      <div className="grid gap-6 sm:grid-cols-2">{([['Strengths', report.strengths], ['Areas to improve', report.areas_to_improve]] as const).map(([title, items]) => <Card key={title} className="p-6"><h2 className="font-semibold">{title}</h2><ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-600">{items.map(v => <li key={v}>{v}</li>)}</ul>{!items.length && <p className="mt-3 text-sm text-slate-500">No recorded observations.</p>}</Card>)}</div>
      <Card className="p-6"><h2 className="font-semibold">Skill evidence</h2><p className="mt-2 text-sm text-slate-500">Question correctness is a proxy for associated skills. Untested skills are not classified as missing.</p><div className="mt-4 space-y-3">{report.skill_evidence.map(s => <details key={s.skill} className="rounded-lg border border-line p-4"><summary className="cursor-pointer font-medium">{s.skill} · {s.status.replaceAll('_', ' ')} · {score(s.score)}</summary>{s.evidence.map((e, i) => <p key={i} className="mt-3 text-sm text-slate-600">{e.reason}</p>)}</details>)}</div></Card>
      <Card className="p-6"><h2 className="font-semibold">Per-question analysis</h2><div className="mt-4 space-y-3">{report.per_question_analysis.map(q => <details key={q.answer_id} className="rounded-lg border border-line p-4"><summary className="cursor-pointer">Question {q.question_number} · {q.topic} · {q.answer_modality} · {score(q.scores.overall_score)}</summary><p className="mt-4 font-medium">{q.question}</p><p className="mt-2 text-xs text-slate-500">Session {q.interview_id} · Skills: {q.expected_skills.join(', ') || q.topic}</p><p className="mt-3 whitespace-pre-wrap break-words rounded-lg bg-surface-muted p-4 text-sm">{q.answer_text}</p><div className="mt-3 flex flex-wrap gap-3 text-xs">{Object.entries(q.scores).map(([k,v]) => <span key={k} className="capitalize">{label(k)}: {score(v)}</span>)}</div><p className="mt-3 text-sm">{q.feedback}</p><p className="mt-2 text-xs text-slate-500">{q.confidence_rationale}</p><p className="mt-3 text-sm">Strengths: {q.strengths.join('; ')}</p><p className="mt-2 text-sm">Improve: {[...q.weaknesses, ...q.missing_points].join('; ')}</p>{q.visual_analysis ? <p className="mt-3 text-sm">Video: {q.visual_analysis.observations.join('; ')} · {q.visual_analysis.common_expressions.join(', ')}</p> : <p className="mt-3 text-xs text-slate-500">Visual observations: not assessed</p>}</details>)}</div></Card>
      <Card className="p-6"><h2 className="font-semibold">Readiness and next steps</h2><p className="mt-3 text-slate-600">{report.summary}</p><ul className="mt-4 list-disc space-y-2 pl-5 text-sm">{report.recommended_focus_areas.map(v => <li key={v}>{v}</li>)}</ul></Card>
    </>)}
  </div>;
}
