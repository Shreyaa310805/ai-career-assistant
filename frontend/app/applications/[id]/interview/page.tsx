"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, Button, Card, CardHeader, Field, LinkButton, Select, cx } from "@/components/ui";
import {
  createInterview,
  interviewSessionPath,
  listInterviews,
  MAX_INTERVIEW_QUESTIONS,
  type InterviewDifficulty,
  type InterviewMode,
  type InterviewPersonality,
  type InterviewSummary,
} from "@/lib/interviews";

const QUESTION_COUNT_OPTIONS = Array.from({ length: MAX_INTERVIEW_QUESTIONS }, (_, index) => index + 1);

const PERSONALITIES: Array<{ value: InterviewPersonality; label: string; description: string }> = [
  { value: "technical", label: "Technical", description: "Focus on role-specific skills and problem solving." },
  { value: "friendly", label: "Friendly", description: "A supportive, conversational practice style." },
  { value: "strict", label: "Strict", description: "A direct, demanding interview practice style." },
  { value: "behavioral", label: "Behavioral", description: "Focus on experience, judgment, and communication." },
  { value: "mixed", label: "Mixed", description: "A balanced blend of technical and behavioral practice." },
];

const DIFFICULTIES: Array<{ value: InterviewDifficulty; label: string; description: string }> = [
  { value: "easy", label: "Easy", description: "Build confidence with foundational questions." },
  { value: "medium", label: "Medium", description: "Practice realistic role-level questions." },
  { value: "hard", label: "Hard", description: "Prepare for deeper, more challenging conversations." },
];

const MODES: Array<{ value: InterviewMode; label: string; description: string }> = [
  { value: "text", label: "Text", description: "Type your answers." },
  { value: "audio", label: "Audio", description: "Speak your answers; they're transcribed and scored." },
  {
    value: "video",
    label: "Video",
    description: "A live on-camera interview. Answers are spoken and final, and your on-camera presence is scored.",
  },
];

export default function InterviewSetupPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const applicationId = params?.id;
  const [personality, setPersonality] = useState<InterviewPersonality>("technical");
  const [difficulty, setDifficulty] = useState<InterviewDifficulty>("medium");
  const [questionTarget, setQuestionTarget] = useState(5);
  const [mode, setMode] = useState<InterviewMode>("text");
  const [error, setError] = useState("");
  const [isStarting, setIsStarting] = useState(false);

  const [isCheckingHistory, setIsCheckingHistory] = useState(true);
  const [resumable, setResumable] = useState<InterviewSummary | null>(null);

  useEffect(() => {
    if (!applicationId) {
      setIsCheckingHistory(false);
      return;
    }
    listInterviews(applicationId, 1, 25)
      .then((response) => {
        const incomplete = response.data?.items.find((item) => item.status !== "completed");
        setResumable(incomplete ?? null);
      })
      .catch(() => {
        // A failed history check should never block starting a fresh session.
      })
      .finally(() => setIsCheckingHistory(false));
  }, [applicationId]);

  async function startInterview() {
    if (!applicationId) {
      setError("This application link is missing an ID.");
      return;
    }
    setError("");
    setIsStarting(true);
    try {
      const response = await createInterview(applicationId, personality, difficulty, questionTarget, mode);
      if (!response.success || !response.data) {
        setError(response.error?.message ?? "Unable to create an interview session. Please try again.");
        return;
      }
      router.push(interviewSessionPath(response.data.interview_id, response.data.mode));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to create an interview session. Please try again.");
      setIsStarting(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Set up interview practice"
          description="Choose the practice style and level for this application."
          action={
            <LinkButton href={`/applications/${applicationId}/interview/history`} variant="secondary" size="sm">
              Past sessions
            </LinkButton>
          }
        />
        <div className="space-y-6 p-6">
          {error ? <Alert>{error}</Alert> : null}
          {!isCheckingHistory && resumable ? (
            <Alert tone="info">
              You have a session in progress ({resumable.answered_count}/{resumable.question_target ?? resumable.question_count}{" "}
              answered).{" "}
              <a className="font-semibold underline" href={interviewSessionPath(resumable.interview_id, resumable.mode)}>
                Resume it
              </a>{" "}
              or view it from{" "}
              <a className="font-semibold underline" href={`/applications/${applicationId}/interview/history`}>
                Session history
              </a>
              .
            </Alert>
          ) : null}
          <fieldset>
            <legend className="text-sm font-medium text-slate-700">Interview mode</legend>
            <div className="mt-2 grid gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Interview mode">
              {MODES.map((option) => (
                <label
                  key={option.value}
                  className={cx(
                    "flex cursor-pointer flex-col gap-1 rounded-lg border p-4 transition-colors",
                    mode === option.value
                      ? "border-brand-500 bg-brand-50/60 ring-1 ring-brand-500"
                      : "border-line bg-white hover:border-line-strong",
                  )}
                >
                  <span className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <input
                      type="radio"
                      name="interview-mode"
                      value={option.value}
                      checked={mode === option.value}
                      onChange={() => setMode(option.value)}
                      className="accent-brand-600"
                    />
                    {option.label}
                  </span>
                  <span className="text-xs leading-5 text-slate-500">{option.description}</span>
                </label>
              ))}
            </div>
            {mode === "video" ? (
              <p className="mt-2 text-xs text-slate-500">
                Your browser will ask for camera and microphone access when the video interview opens.
              </p>
            ) : null}
          </fieldset>
          <Field label="Interview personality" hint={PERSONALITIES.find((option) => option.value === personality)?.description}>
            <Select value={personality} onChange={(event) => setPersonality(event.target.value as InterviewPersonality)}>
              {PERSONALITIES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Difficulty" hint={DIFFICULTIES.find((option) => option.value === difficulty)?.description}>
            <Select value={difficulty} onChange={(event) => setDifficulty(event.target.value as InterviewDifficulty)}>
              {DIFFICULTIES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Number of questions" hint={`Sessions can include up to ${MAX_INTERVIEW_QUESTIONS} questions.`}>
            <Select value={questionTarget} onChange={(event) => setQuestionTarget(Number(event.target.value))}>
              {QUESTION_COUNT_OPTIONS.map((count) => (
                <option key={count} value={count}>
                  {count} question{count === 1 ? "" : "s"}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line pt-5">
            <p className="text-sm text-slate-500">This creates a saved interview session, then you can generate role-specific questions.</p>
            <Button size="lg" onClick={startInterview} disabled={isStarting || !applicationId}>
              {isStarting ? "Starting interview…" : "Start Interview"}
            </Button>
          </div>
        </div>
      </Card>
      <Card className="bg-surface-muted/60 p-6">
        <h2 className="text-[15px] font-semibold">What happens next</h2>
        <p className="mt-1.5 text-sm leading-6 text-slate-500">
          This session uses the current application’s role, job description, resume skills, and ATS context when available.
          Questions get harder or easier from question 3 onward based on how you're doing, and each answer is scored for
          both quality and confidence.
        </p>
      </Card>
    </div>
  );
}
