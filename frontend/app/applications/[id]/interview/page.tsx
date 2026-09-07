"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, Field, LinkButton, Select } from "@/components/ui";
import {
  createInterview,
  generateInterviewQuestion,
  type InterviewDifficulty,
  type InterviewPersonality,
  type InterviewQuestion,
  type InterviewSession,
} from "@/lib/interviews";

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

export default function InterviewPage() {
  const params = useParams<{ id: string }>();
  const applicationId = params?.id;
  const [personality, setPersonality] = useState<InterviewPersonality>("technical");
  const [difficulty, setDifficulty] = useState<InterviewDifficulty>("medium");
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [error, setError] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [question, setQuestion] = useState<InterviewQuestion | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  async function startInterview() {
    if (!applicationId) {
      setError("This application link is missing an ID.");
      return;
    }
    setError("");
    setIsStarting(true);
    try {
      const response = await createInterview(applicationId, personality, difficulty);
      if (!response.success || !response.data) {
        setError(response.error?.message ?? "Unable to create an interview session. Please try again.");
        return;
      }
      setSession(response.data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to create an interview session. Please try again.");
    } finally {
      setIsStarting(false);
    }
  }

  async function generateQuestion() {
    if (!session) return;
    setError("");
    setIsGenerating(true);
    try {
      const response = await generateInterviewQuestion(session.interview_id);
      if (!response.success || !response.data) {
        setError(response.error?.message ?? "Unable to generate a question. Please try again.");
        return;
      }
      setQuestion(response.data);
      setSession({ ...session, question_count: response.data.question_number });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to generate a question. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  }

  if (session) {
    return (
      <Card>
        <CardHeader title="Interview session created" description="Your preferences have been saved for this application." />
        <div className="space-y-6 p-6">
          {error ? <Alert>{error}</Alert> : null}
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="success">Ready</Badge>
            <Badge tone="brand">{labelFor(PERSONALITIES, session.personality)}</Badge>
            <Badge>{labelFor(DIFFICULTIES, session.difficulty)}</Badge>
          </div>
          <dl className="grid gap-4 rounded-lg border border-line bg-surface-muted/60 p-4 sm:grid-cols-2">
            <Info label="Session ID" value={session.interview_id} mono />
            <Info label="Status" value="Created" />
            <Info label="Personality" value={labelFor(PERSONALITIES, session.personality)} />
            <Info label="Difficulty" value={labelFor(DIFFICULTIES, session.difficulty)} />
          </dl>
          {question ? (
            <section className="rounded-lg border border-line bg-surface-muted/60 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm font-semibold">Question {question.question_number}</p>
                <div className="flex gap-2"><Badge tone="brand">{question.topic}</Badge><Badge>{labelFor(DIFFICULTIES, question.difficulty)}</Badge></div>
              </div>
              <p className="mt-4 text-base leading-7 text-slate-800">{question.question}</p>
              {question.expected_skills.length ? <p className="mt-3 text-sm text-slate-500">Expected skills: {question.expected_skills.join(", ")}</p> : null}
            </section>
          ) : <Alert tone="info">Generate your first question to begin practice for this application.</Alert>}
          <div className="flex flex-wrap gap-3">
            <Button onClick={generateQuestion} disabled={isGenerating}>
              {isGenerating ? "Generating questionâ€¦" : question ? "Next Question" : "Generate First Question"}
            </Button>
            <LinkButton href={`/applications/${applicationId}`} variant="secondary">
              Back to application
            </LinkButton>
            <Button variant="ghost" onClick={() => setSession(null)}>
              Create another session
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Set up interview practice" description="Choose the practice style and level for this application." />
        <div className="space-y-6 p-6">
          {error ? <Alert>{error}</Alert> : null}
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
        </p>
      </Card>
    </div>
  );
}

function labelFor(options: Array<{ value: string; label: string }>, value: string) {
  return options.find((option) => option.value === value)?.label ?? value;
}

function Info({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className={mono ? "mt-1 break-all font-mono text-xs text-slate-700" : "mt-1 text-sm text-slate-700"}>{value}</dd>
    </div>
  );
}
