"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, Field, LinkButton, Select } from "@/components/ui";
import {
  createInterview,
  type InterviewDifficulty,
  type InterviewPersonality,
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

  if (session) {
    return (
      <Card>
        <CardHeader title="Interview session created" description="Your preferences have been saved for this application." />
        <div className="space-y-6 p-6">
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
          <Alert tone="info">Session setup is complete. Question generation and live practice will be added in a future step.</Alert>
          <div className="flex flex-wrap gap-3">
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
            <p className="text-sm text-slate-500">This creates a saved interview session. No questions are generated yet.</p>
            <Button size="lg" onClick={startInterview} disabled={isStarting || !applicationId}>
              {isStarting ? "Starting interview…" : "Start Interview"}
            </Button>
          </div>
        </div>
      </Card>
      <Card className="bg-surface-muted/60 p-6">
        <h2 className="text-[15px] font-semibold">What happens next</h2>
        <p className="mt-1.5 text-sm leading-6 text-slate-500">
          This session is connected to the current application. Its role and job description will be available when question generation is introduced.
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
