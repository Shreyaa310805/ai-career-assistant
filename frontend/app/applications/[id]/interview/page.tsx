"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert, Button, Card, CardHeader, Field, LinkButton, Select } from "@/components/ui";
import {
  createInterview,
  listInterviews,
  MAX_INTERVIEW_QUESTIONS,
  type InterviewDifficulty,
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

export default function InterviewSetupPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const applicationId = params?.id;
  const [personality, setPersonality] = useState<InterviewPersonality>("technical");
  const [difficulty, setDifficulty] = useState<InterviewDifficulty>("medium");
  const [questionTarget, setQuestionTarget] = useState(5);
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
      const response = await createInterview(applicationId, personality, difficulty, questionTarget);
      if (!response.success || !response.data) {
        setError(response.error?.message ?? "Unable to create an interview session. Please try again.");
        return;
      }
      router.push(`/interview-session/${response.data.interview_id}`);
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
              <a className="font-semibold underline" href={`/interview-session/${resumable.interview_id}`}>
                Resume it
              </a>{" "}
              or view it from{" "}
              <a className="font-semibold underline" href={`/applications/${applicationId}/interview/history`}>
                Session history
              </a>
              .
            </Alert>
          ) : null}
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
