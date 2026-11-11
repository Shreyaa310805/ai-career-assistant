"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, LinkButton, Skeleton, Textarea } from "@/components/ui";
import { getToken } from "@/lib/auth";
import {
  evaluateFreeInterviewAnswer,
  generateFreeInterviewQuestion,
  getFreeInterview,
  submitFreeInterviewAnswer,
} from "@/lib/free-interview";
import type { InterviewFullSession } from "@/lib/interviews";

export default function FreeInterviewSessionPage() {
  const params = useParams<{ interviewId: string }>();
  const router = useRouter();
  const interviewId = params?.interviewId;
  const [session, setSession] = useState<InterviewFullSession | null>(null);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!interviewId) return;
    const response = await getFreeInterview(interviewId);
    if (!response.success || !response.data) {
      throw new Error(response.error?.message ?? "Unable to load the interview.");
    }
    setSession(response.data);
    const last = response.data.items.at(-1);
    setAnswer(last?.answer?.answer_text ?? "");
  }, [interviewId]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    refresh()
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load the interview."))
      .finally(() => setLoading(false));
  }, [refresh, router]);

  const current = session?.items.at(-1) ?? null;

  async function nextQuestion() {
    if (!interviewId) return;
    setBusy(true);
    setError("");
    try {
      const response = await generateFreeInterviewQuestion(interviewId);
      if (!response.success || !response.data) {
        throw new Error(response.error?.message ?? "Unable to generate the next question.");
      }
      await refresh();
      setAnswer("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to generate the next question.");
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer() {
    if (!interviewId || !current || !answer.trim()) return;
    setBusy(true);
    setError("");
    try {
      const submitted = await submitFreeInterviewAnswer(interviewId, current.question.question_id, answer);
      if (!submitted.success || !submitted.data) {
        throw new Error(submitted.error?.message ?? "Unable to save your answer.");
      }
      const evaluated = await evaluateFreeInterviewAnswer(interviewId, submitted.data.answer_id);
      if (!evaluated.success || !evaluated.data) {
        throw new Error(evaluated.error?.message ?? "Your answer was saved, but feedback could not be generated.");
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit your answer.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-surface-muted">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <div>
            <p className="font-bold tracking-tight text-slate-900">Skill<span className="text-brand-600">Sync</span></p>
            <p className="mt-1 text-xs font-semibold uppercase tracking-[0.14em] text-brand-600">Free text interview</p>
          </div>
          <div className="flex gap-2">
            <LinkButton href="/upgrade" size="sm">Upgrade</LinkButton>
            <LinkButton href="/dashboard" size="sm" variant="secondary">Exit interview</LinkButton>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-4xl space-y-6 px-5 py-8 sm:px-8">
        {loading ? (
          <Skeleton className="h-72 w-full" />
        ) : error && !session ? (
          <Card className="space-y-4 p-6"><Alert>{error}</Alert><LinkButton href="/dashboard" variant="secondary">Back to dashboard</LinkButton></Card>
        ) : session ? (
          <>
            <Card className="p-6 sm:p-8">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <Badge tone="brand">Text only</Badge>
                  <h1 className="mt-3 text-2xl font-bold tracking-tight">
                    {session.status === "completed" ? "Interview complete" : `Question ${session.items.length} of ${session.question_target}`}
                  </h1>
                  <p className="mt-2 text-sm text-slate-500">Three questions · one free session</p>
                </div>
                {session.average_score != null ? (
                  <div className="rounded-xl bg-brand-50 px-4 py-3 text-center">
                    <p className="text-xs text-brand-700">Average score</p>
                    <p className="text-2xl font-bold text-brand-800">{Math.round(session.average_score)}%</p>
                  </div>
                ) : null}
              </div>

              {error ? <div className="mt-5"><Alert>{error}</Alert></div> : null}

              {session.status === "completed" ? (
                <div className="mt-6 space-y-5">
                  <p className="text-sm leading-6 text-slate-600">You’ve completed all three questions. Upgrade to Premium for additional interviews and preparation tools.</p>
                  <div className="flex flex-wrap gap-3">
                    <LinkButton href="/upgrade">Explore Premium</LinkButton>
                    <LinkButton href="/dashboard" variant="secondary">Back to dashboard</LinkButton>
                  </div>
                </div>
              ) : !current ? (
                <div className="mt-6">
                  <Button onClick={nextQuestion} disabled={busy}>{busy ? "Preparing question…" : "Start question 1"}</Button>
                </div>
              ) : (
                <div className="mt-7 space-y-5">
                  <div className="rounded-xl bg-surface-muted p-5">
                    <div className="mb-3 flex flex-wrap gap-2">
                      <Badge tone="brand">{current.question.topic}</Badge>
                      <Badge>{current.question.difficulty}</Badge>
                    </div>
                    <p className="text-lg leading-8 text-slate-900">{current.question.question}</p>
                  </div>

                  {current.evaluation ? (
                    <div className="space-y-4 rounded-xl border border-line p-5">
                      <div className="flex items-center justify-between gap-3">
                        <h2 className="font-semibold">Feedback</h2>
                        <Badge tone="brand">{current.evaluation.overall_score}/100</Badge>
                      </div>
                      <p className="text-sm leading-6 text-slate-600">{current.evaluation.feedback}</p>
                      {current.evaluation.strengths.length ? (
                        <div>
                          <h3 className="text-sm font-semibold">What went well</h3>
                          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
                            {current.evaluation.strengths.map((item) => <li key={item}>{item}</li>)}
                          </ul>
                        </div>
                      ) : null}
                      {current.evaluation.missing_points.length ? (
                        <div>
                          <h3 className="text-sm font-semibold">Consider adding</h3>
                          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
                            {current.evaluation.missing_points.map((item) => <li key={item}>{item}</li>)}
                          </ul>
                        </div>
                      ) : null}
                      {session.items.length < session.question_target ? (
                        <Button onClick={nextQuestion} disabled={busy}>{busy ? "Preparing…" : "Next question"}</Button>
                      ) : null}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <label className="block">
                        <span className="label">Your answer</span>
                        <Textarea
                          className="mt-1.5 min-h-40"
                          value={answer}
                          onChange={(event) => setAnswer(event.target.value)}
                          maxLength={12000}
                          placeholder="Write your answer here…"
                        />
                      </label>
                      <Button onClick={submitAnswer} disabled={busy || !answer.trim()}>
                        {busy ? "Saving and reviewing…" : "Submit answer"}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </Card>
          </>
        ) : null}
      </div>
    </main>
  );
}
