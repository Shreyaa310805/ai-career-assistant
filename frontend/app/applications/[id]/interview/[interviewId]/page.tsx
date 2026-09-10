"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Alert, Badge, Card, CardHeader, LinkButton, Skeleton } from "@/components/ui";
import { SessionSummaryCard } from "@/components/interview-summary-card";
import { MetricBar, ScoreDial, ScoreTrendChart, type TrendPoint } from "@/components/interview-charts";
import { getInterviewFull, type InterviewFullSession } from "@/lib/interviews";

export default function InterviewReviewPage() {
  const params = useParams<{ id: string; interviewId: string }>();
  const applicationId = params?.id;
  const interviewId = params?.interviewId;
  const [session, setSession] = useState<InterviewFullSession | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!interviewId) return;
    getInterviewFull(interviewId)
      .then((response) => {
        if (!response.success || !response.data) {
          setError(response.error?.message ?? "Unable to load this interview session.");
          return;
        }
        setSession(response.data);
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
          <LinkButton href={`/applications/${applicationId}/interview/history`} variant="secondary" size="sm">
            Back to history
          </LinkButton>
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
                averageConfidence={session.average_confidence}
              />
            ) : (
              <Alert tone="info">
                This session is not marked complete yet.{" "}
                <a className="font-semibold underline" href={`/interview-session/${interviewId}`}>
                  Continue it
                </a>{" "}
                to keep answering questions.
              </Alert>
            )}

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
                        <ScoreDial label="Confidence" value={evaluation.confidence_score} size="sm" />
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
