"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Alert, Badge, Card, CardHeader, LinkButton, Skeleton } from "@/components/ui";
import { SessionSummaryCard } from "@/components/interview-summary-card";
import { MetricBar, ScoreDial, ScoreTrendChart, type TrendPoint } from "@/components/interview-charts";
import { getInterviewFull, interviewSessionPath, type InterviewFullSession, type VisualAnalysis } from "@/lib/interviews";
import { getSessionInterviewReport, type SessionInterviewReport } from "@/lib/interview-reports";

export default function InterviewReviewPage() {
  const params = useParams<{ id: string; interviewId: string }>();
  const applicationId = params?.id;
  const interviewId = params?.interviewId;
  const [session, setSession] = useState<InterviewFullSession | null>(null);
  const [error, setError] = useState("");
  const [report, setReport] = useState<SessionInterviewReport | null>(null);

  useEffect(() => {
    if (!interviewId) return;
    getInterviewFull(interviewId)
      .then((response) => {
        if (!response.success || !response.data) {
          setError(response.error?.message ?? "Unable to load this interview session.");
          return;
        }
        setSession(response.data);
        if (response.data.status === "completed") {
          getSessionInterviewReport(interviewId).then(r => setReport(r.data)).catch((e: Error) => setError(e.message));
        }
      })
      .catch((requestError: Error) => setError(requestError.message));
  }, [interviewId]);

  const evaluatedItems = useMemo(() => session?.items.filter((item) => item.evaluation) ?? [], [session]);

  const trendPoints: TrendPoint[] = useMemo(
    () =>
      (session?.items ?? []).map((item) => ({
        label: `Q${item.question.question_number}`,
        value: item.evaluation ? Math.round(item.evaluation.overall_score) : null,
      })),
    [session],
  );

  const dimensionAverages = useMemo(() => {
    if (!evaluatedItems.length) return null;
    const dims: Array<[string, keyof NonNullable<InterviewFullSession["items"][number]["evaluation"]>]> = [
      ["Relevance", "relevance_score"],
      ["Correctness", "correctness_score"],
      ["Depth", "depth_score"],
      ["Clarity", "clarity_score"],
      ["Evidence", "evidence_score"],
    ];
    return dims.map(([label, key]) => ({
      label,
      value: evaluatedItems.reduce((sum, item) => sum + (item.evaluation![key] as number), 0) / evaluatedItems.length,
    }));
  }, [evaluatedItems]);

  const improvements = useMemo(() => {
    const points = new Map<string, number>();
    for (const item of evaluatedItems) {
      for (const point of [...item.evaluation!.weaknesses, ...item.evaluation!.missing_points]) {
        points.set(point, (points.get(point) ?? 0) + 1);
      }
    }
    return Array.from(points.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([point]) => point);
  }, [evaluatedItems]);

  return (
    <Card>
      <CardHeader
        title="Interview results"
        description="A detailed breakdown of this practice session's scores, confidence, and feedback."
        action={
          <div className="flex gap-2"><LinkButton href={`/applications/${applicationId}/interview/report`} variant="secondary" size="sm">Application report</LinkButton><LinkButton href={`/applications/${applicationId}/interview/history`} variant="secondary" size="sm">
            Back to history
          </LinkButton></div>
        }
      />
      <div className="space-y-8 p-6">
        {error ? <Alert>{error}</Alert> : null}
        {!session && !error ? (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : null}
        {session ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="brand">{session.personality}</Badge>
              <Badge>{session.difficulty}</Badge>
              {session.mode !== "text" ? <Badge tone="info">{session.mode === "video" ? "Video" : "Audio"}</Badge> : null}
              <Badge tone={session.status === "completed" ? "success" : "info"}>
                {session.status === "completed" ? "Completed" : session.status === "in_progress" ? "In progress" : "Not started"}
              </Badge>
              <span className="text-xs text-slate-400">
                {session.items.length}/{session.question_target} questions
              </span>
            </div>

            {session.status === "completed" && session.summary ? (
              <SessionSummaryCard
                summary={session.summary}
                recommendation={session.recommendation ?? ""}
                averageScore={session.average_score}
                averageConfidence={report?.confidence_score ?? null}
              />
            ) : (
              <Alert tone="info">
                This session is not marked complete yet.{" "}
                <a className="font-semibold underline" href={interviewSessionPath(session.interview_id, session.mode)}>
                  Continue it
                </a>{" "}
                to keep answering questions.
              </Alert>
            )}

            {report ? <section className="rounded-card border border-line bg-white p-5"><h3 className="font-semibold">{report.readiness}</h3><p className="mt-2 text-sm text-slate-500">{report.questions_attempted} attempted · {report.questions_evaluated} evaluated</p><div className="mt-4 grid gap-4 sm:grid-cols-2">{(["verbal_confidence", "visual_confidence"] as const).map(key => <div key={key}><p className="text-sm font-medium capitalize">{key.replaceAll('_', ' ')}: {report[key].score === null ? 'Not assessed' : `${report[key].score} / 100`}</p><p className="mt-1 text-xs text-slate-500">{report[key].basis}</p></div>)}</div></section> : null}

            {session.mode === "video" ? (
              <VisualAnalysisSection analysis={session.visual_analysis} completed={session.status === "completed"} />
            ) : null}

            {evaluatedItems.length ? (
              <div className="grid gap-6 lg:grid-cols-2">
                <section className="rounded-card border border-line bg-white p-5">
                  <h3 className="text-sm font-semibold text-slate-900">Score by question</h3>
                  <p className="mt-1 text-xs text-slate-500">How the overall score trended across the session.</p>
                  <div className="mt-5">
                    <ScoreTrendChart points={trendPoints} />
                  </div>
                </section>
                <section className="rounded-card border border-line bg-white p-5">
                  <h3 className="text-sm font-semibold text-slate-900">Average by dimension</h3>
                  <p className="mt-1 text-xs text-slate-500">Where answers were strongest and weakest, on average.</p>
                  <div className="mt-5 space-y-4">
                    {dimensionAverages?.map((dimension) => (
                      <MetricBar key={dimension.label} label={dimension.label} value={dimension.value} />
                    ))}
                  </div>
                </section>
              </div>
            ) : null}

            {improvements.length ? (
              <section className="rounded-card border border-amber-100 bg-amber-50/50 p-5">
                <h3 className="text-sm font-semibold text-amber-900">What to improve next time</h3>
                <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                  {improvements.map((point) => (
                    <li key={point} className="flex items-start gap-2 rounded-lg bg-white/70 px-3 py-2 text-sm text-amber-900">
                      <span aria-hidden className="mt-0.5 text-amber-500">
                        ↗
                      </span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            <section className="space-y-4">
              <h3 className="text-sm font-semibold text-slate-900">Questions &amp; answers</h3>
              {session.items.map(({ question, answer, evaluation }) => (
                <section key={question.question_id} className="rounded-card border border-line bg-white p-5 shadow-xs">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold">Question {question.question_number}</p>
                    <div className="flex gap-2">
                      <Badge tone="brand">{question.topic}</Badge>
                      <Badge>{question.difficulty}</Badge>
                    </div>
                  </div>
                  <p className="mt-4 text-base leading-7 text-slate-800">{question.question}</p>
                  {answer ? (
                    <div className="mt-4 rounded-lg border border-line bg-surface-muted/60 p-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Your answer</p>
                      <p className="mt-1.5 text-sm leading-6 text-slate-700">{answer.answer_text}</p>
                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-slate-500">This question was not answered.</p>
                  )}
                  {evaluation ? (
                    <div className="mt-4 grid gap-5 rounded-lg border border-brand-100 bg-brand-50/30 p-4 sm:grid-cols-[auto_1fr]">
                      <div className="flex gap-3 sm:flex-col">
                        <ScoreDial label="Score" value={evaluation.overall_score} size="sm" />
                        <ScoreDial label="Language confidence" value={report?.per_question_analysis.find(q => q.answer_id === answer?.answer_id)?.scores.confidence_score ?? null} size="sm" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm leading-6 text-slate-700">{evaluation.feedback}</p>
                        <p className="mt-2 text-xs text-slate-500">{evaluation.confidence_rationale}</p>
                        {evaluation.strengths.length ? (
                          <p className="mt-3 text-sm text-slate-700">
                            <span className="font-semibold text-emerald-700">Strengths:</span> {evaluation.strengths.join(" ")}
                          </p>
                        ) : null}
                        {evaluation.weaknesses.length ? (
                          <p className="mt-2 text-sm text-slate-700">
                            <span className="font-semibold text-amber-700">Improve:</span> {evaluation.weaknesses.join(" ")}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                </section>
              ))}
            </section>
          </>
        ) : null}
      </div>
    </Card>
  );
}

function VisualAnalysisSection({ analysis, completed }: { analysis: VisualAnalysis | null; completed: boolean }) {
  if (!analysis) {
    return (
      <section className="rounded-card border border-line bg-surface-muted/60 p-5">
        <h3 className="text-sm font-semibold text-slate-900">On-camera presence</h3>
        <p className="mt-1 text-sm text-slate-500">
          {completed
            ? "No camera frames were analyzed during this session, so no visual score was generated."
            : "The visual score is generated from sampled camera frames when the interview ends."}
        </p>
      </section>
    );
  }
  const metrics = [
    { label: "Engagement", value: analysis.engagement },
    { label: "Attentiveness", value: analysis.attentiveness },
    { label: "Composure", value: analysis.composure },
    { label: "Presentation", value: analysis.presentation },
    { label: "Eye contact", value: analysis.eye_contact_rate * 100 },
    { label: "Visible on camera", value: analysis.face_visible_rate * 100 },
  ];
  return (
    <section className="rounded-card border border-line bg-white p-5">
      <div className="flex flex-wrap items-start gap-6">
        <ScoreDial label="Visual" value={analysis.visual_score} size="lg" />
        <div className="min-w-[220px] flex-1">
          <h3 className="text-sm font-semibold text-slate-900">On-camera presence</h3>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Based on {analysis.frames_analyzed} camera frame{analysis.frames_analyzed === 1 ? "" : "s"} sampled at random
            moments during the interview. It reflects observable signals only — visibility, gaze direction, framing and
            expression steadiness — not personality or emotions. It is reported separately from your answer score.
          </p>
          {analysis.frames_analyzed < 3 ? (
            <p className="mt-2 text-xs text-amber-700">Only a few frames were analyzed, so treat this as a rough indicator.</p>
          ) : null}
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {metrics.map((metric) => (
              <MetricBar key={metric.label} label={metric.label} value={metric.value} />
            ))}
          </div>
          {analysis.common_expressions.length ? (
            <div className="mt-4 flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-slate-500">Most common expressions:</span>
              {analysis.common_expressions.map((expression) => (
                <span key={expression} className="rounded-full bg-surface-sunken px-2.5 py-1 text-xs text-slate-600">
                  {expression}
                </span>
              ))}
            </div>
          ) : null}
          {analysis.observations.length ? (
            <ul className="mt-4 space-y-1.5 text-sm text-slate-600">
              {analysis.observations.map((observation) => (
                <li key={observation}>• {observation}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}
