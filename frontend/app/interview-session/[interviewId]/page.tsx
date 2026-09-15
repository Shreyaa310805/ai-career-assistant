"use client";

import { AudioAnswerRecorder } from "@/components/audio-answer-recorder";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Alert, Badge, Button, Card, Field, Skeleton, Textarea } from "@/components/ui";
import { ScoreDial } from "@/components/interview-charts";
import { getToken } from "@/lib/auth";
import { getApplication, type Application } from "@/lib/applications";
import {
  completeInterview,
  evaluateInterviewAnswer,
  generateInterviewQuestion,
  getInterviewFull,
  submitInterviewAnswer,
  submitInterviewAudio,
  type InterviewAnswerEvaluation,
  type InterviewDifficulty,
  type InterviewPersonality,
  type InterviewQuestion,
} from "@/lib/interviews";

const PERSONALITY_LABEL: Record<InterviewPersonality, string> = {
  technical: "Technical",
  friendly: "Friendly",
  strict: "Strict",
  behavioral: "Behavioral",
  mixed: "Mixed",
};

const DIFFICULTY_LABEL: Record<InterviewDifficulty, string> = { easy: "Easy", medium: "Medium", hard: "Hard" };

/**
 * A distraction-free, full-screen practice room: no app sidebar, no
 * application tabs — just this session's question, answer, and the two
 * ways to leave it (Go Back / End Session).
 */
export default function InterviewSessionPage() {
  const params = useParams<{ interviewId: string }>();
  const router = useRouter();
  const interviewId = params?.interviewId;

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [company, setCompany] = useState<string | null>(null);
  const [personality, setPersonality] = useState<InterviewPersonality>("technical");
  const [difficulty, setDifficulty] = useState<InterviewDifficulty>("medium");
  const [answeredCount, setAnsweredCount] = useState(0);
  const [questionTarget, setQuestionTarget] = useState(5);

  const [question, setQuestion] = useState<InterviewQuestion | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [answerText, setAnswerText] = useState("");
  const [submittedAnswerId, setSubmittedAnswerId] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<InterviewAnswerEvaluation | null>(null);
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false);
  const [questionStartedAt, setQuestionStartedAt] = useState<number | null>(null);
  const [answerMode, setAnswerMode] = useState<"typed" | "audio">("audio");
  const [audioBusy, setAudioBusy] = useState(false);
  const [answerStatus, setAnswerStatus] = useState("");
  const submissionLock = useRef(false);
  const [isEnding, setIsEnding] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!interviewId) return;
    getInterviewFull(interviewId)
      .then(async (response) => {
        if (!response.success || !response.data) {
          setError(response.error?.message ?? "Unable to load this interview session.");
          return;
        }
        const full = response.data;
        setApplicationId(full.application_id);
        if (full.status === "completed") {
          // Completed sessions are read-only — the results page owns that view.
          router.replace(`/applications/${full.application_id}/interview/${interviewId}`);
          return;
        }
        if (full.mode === "video") {
          router.replace(`/video-interview/${interviewId}`);
          return;
        }
        setAnswerMode(full.mode === "audio" ? "audio" : "typed");
        setPersonality(full.personality);
        setDifficulty(full.difficulty);
        setQuestionTarget(full.question_target);
        setAnsweredCount(full.items.filter((item) => item.evaluation).length);
        const last = full.items[full.items.length - 1];
        if (last) {
          setQuestion(last.question);
          setAnswerText(last.answer?.answer_text ?? "");
          setSubmittedAnswerId(last.answer?.answer_id ?? null);
          setEvaluation(last.evaluation);
        }
        try {
          const application: Application = await getApplication(full.application_id);
          setCompany(application.company);
        } catch {
          // The session still works without the company name.
        }
      })
      .catch((requestError: Error) => setError(requestError.message))
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interviewId]);

  const questionsAsked = question ? question.question_number : 0;
  const atTarget = questionsAsked >= questionTarget;

  async function generateQuestion() {
    if (!interviewId) return;
    setError("");
    setIsGenerating(true);
    try {
      const response = await generateInterviewQuestion(interviewId);
      if (!response.success || !response.data) {
        setError(response.error?.message ?? "Unable to generate a question. Please try again.");
        return;
      }
      setQuestion(response.data);
      setAnswerText("");
      setSubmittedAnswerId(null);
      setEvaluation(null);
      setQuestionStartedAt(Date.now());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to generate a question. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function submitAndEvaluateAnswer(audio?: Blob, audioDuration?: number) {
    if (!interviewId || !question || submissionLock.current || (!audio && !answerText.trim())) return;
    submissionLock.current = true;
    setError("");
    setIsSubmittingAnswer(true);
    const wasAlreadyEvaluated = Boolean(evaluation);
    try {
      let answerId = submittedAnswerId;
      if (audio || !answerId || answerMode === "typed") {
        setAnswerStatus(audio ? "Uploading and transcribing..." : "Saving answer...");
        const duration = questionStartedAt ? Math.round((Date.now() - questionStartedAt) / 1000) : undefined;
        const submitted = audio
          ? await submitInterviewAudio(interviewId, question.question_id, audio, audioDuration ?? 0)
          : await submitInterviewAnswer(interviewId, question.question_id, answerText, duration);
        if (!submitted.success || !submitted.data) throw new Error(submitted.error?.message ?? "Unable to save answer.");
        answerId = submitted.data.answer_id;
        setSubmittedAnswerId(answerId);
        setAnswerText(submitted.data.answer_text);
        setEvaluation(null);
        if (wasAlreadyEvaluated) setAnsweredCount(count => Math.max(0, count - 1));
      }
      setAnswerStatus("Evaluating...");
      const evaluated = await evaluateInterviewAnswer(interviewId, answerId!);
      if (!evaluated.success || !evaluated.data) throw new Error(evaluated.error?.message ?? "Answer saved. Please retry evaluation.");
      setEvaluation(evaluated.data);
      setAnsweredCount(count => count + 1);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to submit answer. Please retry.");
    } finally {
      setIsSubmittingAnswer(false);
      setAnswerStatus("");
      submissionLock.current = false;
    }
  }

  async function endSession() {
    if (!interviewId || !applicationId) return;
    setError("");
    setIsEnding(true);
    try {
      const response = await completeInterview(interviewId);
      if (!response.success || !response.data) {
        setError(response.error?.message ?? "Unable to end this session. Please try again.");
        setIsEnding(false);
        return;
      }
      router.push(`/applications/${applicationId}/interview/history`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to end this session. Please try again.");
      setIsEnding(false);
    }
  }

  function goBack() {
    if (!applicationId) {
      router.back();
      return;
    }
    router.push(`/applications/${applicationId}/interview`);
  }

  return (
    <main className="min-h-screen bg-surface-muted">
      <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-5 py-4 sm:px-8">
          <div>
            <Link href="/dashboard" className="text-base font-bold tracking-tight text-slate-900">
              Skill<span className="text-brand-600">Sync</span>
            </Link>
            <p className="mt-1 text-xs font-semibold uppercase tracking-[0.14em] text-brand-600">Live practice session</p>
            
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={goBack} disabled={isEnding || audioBusy || isSubmittingAnswer}>
              Go Back
            </Button>
            <Button variant="secondary" size="sm" onClick={endSession} disabled={isEnding || isLoading || audioBusy || isSubmittingAnswer}>
              {isEnding ? "Ending…" : "End Session"}
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-4xl space-y-6 px-5 py-8 pb-24 sm:px-8">
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-72 w-full" />
          </div>
        ) : error && !question ? (
          <Card>
            <div className="space-y-4 p-6">
              <Alert>{error}</Alert>
              <Button variant="secondary" onClick={goBack}>
                Go Back
              </Button>
            </div>
          </Card>
        ) : (
          <>
            <div className="overflow-hidden rounded-card border border-line bg-gradient-to-br from-brand-600 to-brand-800 text-white shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-4 p-6">
                <div>
                  <h2 className="text-2xl font-bold tracking-tight">
                    {question ? `Question ${question.question_number} of ${questionTarget}` : "Ready when you are"}
                  </h2>
                  <p className="mt-1.5 text-sm text-brand-100">
                    {PERSONALITY_LABEL[personality]} style · {DIFFICULTY_LABEL[difficulty]} difficulty
                  </p>
                </div>
                <div className="w-full max-w-[220px]">
                  <div className="flex items-center justify-between text-xs text-brand-100">
                    <span>Progress</span>
                    <span>
                      {answeredCount}/{questionTarget} answered
                    </span>
                  </div>
                  <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-white/20">
                    <div
                      className="h-full rounded-full bg-white"
                      style={{ width: `${Math.min(100, (answeredCount / questionTarget) * 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {error ? <Alert>{error}</Alert> : null}

            {question ? (
              <Card className="overflow-hidden">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface-muted/60 px-6 py-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="brand">{question.topic}</Badge>
                    <Badge>{DIFFICULTY_LABEL[question.difficulty]}</Badge>
                    <Badge tone="neutral">{question.question_type.replace(/_/g, " ")}</Badge>
                  </div>
                  <span className="text-xs font-medium text-slate-500">Question {question.question_number}</span>
                </div>
                <div className="p-6">
                  <p className="text-lg leading-8 text-slate-900">{question.question}</p>
                  {question.expected_skills.length ? (
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {question.expected_skills.map((skill) => (
                        <span key={skill} className="rounded-full bg-surface-sunken px-2.5 py-1 text-xs text-slate-500">
                          {skill}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  <div className="mt-6 space-y-3 border-t border-line pt-6">
                    <div className="flex gap-2" aria-label="Answer mode">
                      <Button variant={answerMode === "audio" ? "primary" : "secondary"} disabled={audioBusy || isSubmittingAnswer} onClick={() => setAnswerMode("audio")}>Audio</Button>
                      <Button variant={answerMode === "typed" ? "primary" : "secondary"} disabled={audioBusy || isSubmittingAnswer} onClick={() => setAnswerMode("typed")}>Text</Button>
                    </div>
                    {answerMode === "audio" ? <>
                      <AudioAnswerRecorder key={question.question_id} disabled={isSubmittingAnswer || isEnding || isGenerating} onBusy={setAudioBusy}
                        onSubmit={(blob, duration) => submitAndEvaluateAnswer(blob, duration)} />
                      {submittedAnswerId && <div><p className="font-semibold">Saved answer / transcript</p><p className="whitespace-pre-wrap">{answerText}</p></div>}
                      {submittedAnswerId && !evaluation && <Button disabled={isSubmittingAnswer || audioBusy} onClick={() => submitAndEvaluateAnswer()}>Retry evaluation</Button>}
                    </> : <>
                      <Field label="Your answer">
                        <Textarea value={answerText} onChange={event => setAnswerText(event.target.value)} rows={7}
                          placeholder="Write your answer here..." disabled={isSubmittingAnswer} />
                      </Field>
                      <Button onClick={() => submitAndEvaluateAnswer()} disabled={isSubmittingAnswer || !answerText.trim()}>Submit answer</Button>
                    </>}
                    {answerStatus && <p role="status">{answerStatus}</p>}
                  </div>

                  {evaluation ? (
                    <div className="mt-6 grid gap-5 rounded-lg border border-line bg-surface-muted/60 p-5 sm:grid-cols-[auto_1fr]">
                      <div className="flex gap-4 sm:flex-col">
                        <ScoreDial label="Score" value={evaluation.overall_score} />
                        <ScoreDial label="Confidence" value={evaluation.confidence_score} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm leading-6 text-slate-700">{evaluation.feedback}</p>
                        <p className="mt-2 text-xs italic text-slate-500">{evaluation.confidence_rationale}</p>
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
                </div>
              </Card>
            ) : (
              <Card>
                <div className="p-10 text-center text-slate-600">Generate your first question when you're ready to begin.</div>
              </Card>
            )}

            <div className="sticky bottom-4 z-10 flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-white/95 p-4 shadow-sm backdrop-blur">
              <p className="text-sm text-slate-500">
                {atTarget
                  ? `You've reached this session's ${questionTarget}-question limit.`
                  : `${questionsAsked}/${questionTarget} questions asked`}
              </p>
              <div className="flex flex-wrap gap-3">
                {!atTarget ? (
                  <Button onClick={generateQuestion} disabled={isGenerating || audioBusy || isSubmittingAnswer}>
                    {isGenerating ? "Generating…" : question ? "Next Question" : "Generate First Question"}
                  </Button>
                ) : null}
                <Button variant="secondary" onClick={endSession} disabled={isEnding || audioBusy || isSubmittingAnswer}>
                  {isEnding ? "Ending…" : "End Session"}
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
