"use client";

import { useEffect, useRef, useState } from "react";
import { getPlan, type PlanDetails } from "@/lib/billing";
import { authedRequest } from "@/lib/auth";
import { Alert, Badge, Button, Card, CardHeader, Field, LinkButton, Select, Textarea } from "@/components/ui";
import {
  createInterview,
  getInterview,
  evaluateInterviewAnswer,
  generateInterviewQuestion,
  submitInterviewAnswer,
  type InterviewAnswerEvaluation,
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

export default function InterviewPractice({ applicationId }: { applicationId?: string }) {
  const [plan, setPlan] = useState<PlanDetails | null>(null);
  const [history, setHistory] = useState<Array<{ session: InterviewSession; is_trial: boolean; credits_charged: number }>>([]);
  const [report, setReport] = useState<{ overall_score: number | null; evaluated_answers: number; evaluations: InterviewAnswerEvaluation[] } | null>(null);
  const storageKey = `interview-session-${applicationId || "practice"}`;
  const requestKey = useRef<string | null>(null);
  const [personality, setPersonality] = useState<InterviewPersonality>("technical");
  const [difficulty, setDifficulty] = useState<InterviewDifficulty>("medium");
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [error, setError] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [question, setQuestion] = useState<InterviewQuestion | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [answerText, setAnswerText] = useState("");
  const [submittedAnswerId, setSubmittedAnswerId] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<InterviewAnswerEvaluation | null>(null);
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false);
  useEffect(() => {
    getPlan().then(setPlan).catch(() => {});
    authedRequest<{ data: Array<{ session: InterviewSession; is_trial: boolean; credits_charged: number }> }>("/practice/interviews")
      .then(r => setHistory(r.data.filter(item => !applicationId || item.session.application_id === applicationId))).catch(() => {});
    const saved = localStorage.getItem(storageKey);
    if (saved) getInterview(saved).then(r => { if (r.data) { setSession(r.data); loadQuestions(saved); } }).catch(() => localStorage.removeItem(storageKey));
  }, [storageKey]);

  async function loadQuestions(id: string) {
    try {
      const r = await authedRequest<{ data: { questions: InterviewQuestion[] } }>(`/interviews/${id}/questions`);
      setQuestion(r.data.questions.at(-1) ?? null);
    } catch { setQuestion(null); }
  }

  async function showReport() {
    if (!session) return;
    setError("");
    try {
      const result = await authedRequest<{ data: { overall_score: number | null; evaluated_answers: number; evaluations: InterviewAnswerEvaluation[] } }>(`/interviews/${session.interview_id}/report`);
      setReport(result.data);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load report"); }
  }

  async function startInterview() {
    setError("");
    setIsStarting(true);
    try {
      if (!requestKey.current) requestKey.current = crypto.randomUUID();
      const response = await createInterview(applicationId, personality, difficulty, requestKey.current);
      if (!response.success || !response.data) {
        setError(response.error?.message ?? "Unable to create an interview session. Please try again.");
        return;
      }
      setSession(response.data);
      setHistory(current => [{ session: response.data!, is_trial: plan?.plan === "FREE", credits_charged: plan?.plan === "FREE" ? 0 : 1 }, ...current]);
      localStorage.setItem(storageKey, response.data.interview_id);
      setPlan(await getPlan());
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
      setAnswerText("");
      setSubmittedAnswerId(null);
      setEvaluation(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to generate a question. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function submitAndEvaluateAnswer() {
    if (!session || !question || !answerText.trim()) return;
    setError("");
    setIsSubmittingAnswer(true);
    try {
      let answerId = submittedAnswerId;
      if (!answerId) {
        const submitted = await submitInterviewAnswer(session.interview_id, question.question_id, answerText);
        if (!submitted.success || !submitted.data) {
          setError(submitted.error?.message ?? "Unable to submit your answer. Please try again.");
          return;
        }
        answerId = submitted.data.answer_id;
        setSubmittedAnswerId(answerId);
      }
      const evaluated = await evaluateInterviewAnswer(session.interview_id, answerId);
      if (!evaluated.success || !evaluated.data) {
        setError(evaluated.error?.message ?? "Your answer was saved, but could not be evaluated yet.");
        return;
      }
      setEvaluation(evaluated.data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to submit your answer. Please try again.");
    } finally {
      setIsSubmittingAnswer(false);
    }
  }

  if (session) {
    return (
      <Card>
        <CardHeader title="Interview session created" description="Your preferences have been saved for this application." />
        <div className="space-y-6 p-6">
          <p>{plan?.plan === "PREMIUM" ? `${plan.credits}/${plan.credit_limit} credits — this session uses no further credits` : `Free trial: up to ${plan?.trial_question_limit ?? "a limited number of"} questions`}</p>
          <Button variant="secondary" onClick={showReport}>View premium report</Button>
          {plan?.plan !== "PREMIUM" && <LinkButton href="/upgrade">Upgrade for Pro interviews and reports</LinkButton>}
          {report && <Alert tone="info">Report: {report.evaluated_answers} evaluated answers. Overall score: {report.overall_score === null ? "Submit and evaluate an answer first" : `${report.overall_score}/100`}.</Alert>}
          {report?.evaluations.map((item, index) => <section key={item.evaluation_id} className="rounded-lg border border-line p-4 space-y-2">
            <h3 className="font-semibold">Answer {index + 1}: {item.overall_score}/100</h3>
            <p>{item.feedback}</p>
            <p className="text-sm">Correctness {item.correctness_score} · Relevance {item.relevance_score} · Reasoning {item.depth_score} · Clarity {item.clarity_score}</p>
            {item.strengths.length > 0 && <p className="text-sm">Strengths: {item.strengths.join(" ")}</p>}
            {item.weaknesses.length > 0 && <p className="text-sm">Improve: {item.weaknesses.join(" ")}</p>}
          </section>)}
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
              <div className="mt-5 space-y-3 border-t border-line pt-5">
                <Field label="Your answer" hint="Your typed answer will be evaluated against this question.">
                  <Textarea value={answerText} onChange={(event) => { setAnswerText(event.target.value); setSubmittedAnswerId(null); setEvaluation(null); }} rows={6} placeholder="Write your answer here..." disabled={isSubmittingAnswer} />
                </Field>
                <Button onClick={submitAndEvaluateAnswer} disabled={isSubmittingAnswer || !answerText.trim()}>
                  {isSubmittingAnswer ? "Submitting and evaluating..." : submittedAnswerId ? "Re-evaluate answer" : "Submit answer"}
                </Button>
              </div>
              {evaluation ? (
                <section className="mt-5 rounded-lg border border-brand-100 bg-brand-50/40 p-4">
                  <p className="text-sm font-semibold text-slate-900">Evaluation: {evaluation.overall_score}/100</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{evaluation.feedback}</p>
                  {evaluation.strengths.length ? <p className="mt-3 text-sm text-slate-700"><span className="font-semibold">Strengths:</span> {evaluation.strengths.join(" ")}</p> : null}
                  {evaluation.weaknesses.length ? <p className="mt-2 text-sm text-slate-700"><span className="font-semibold">Improve:</span> {evaluation.weaknesses.join(" ")}</p> : null}
                </section>
              ) : null}
            </section>
          ) : <Alert tone="info">Generate your first question to begin practice for this application.</Alert>}
          <div className="flex flex-wrap gap-3">
            <Button onClick={generateQuestion} disabled={isGenerating}>
              {isGenerating ? "Generating questionâ€¦" : question ? "Next Question" : "Generate First Question"}
            </Button>
            <LinkButton href={applicationId ? `/applications/${applicationId}` : "/dashboard"} variant="secondary">
              Back to application
            </LinkButton>
            <Button variant="ghost" onClick={() => { setSession(null); setQuestion(null); setReport(null); requestKey.current = null; localStorage.removeItem(storageKey); }}>
              Create another session
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <p>{plan?.plan === "PREMIUM" ? `${plan.credits}/${plan.credit_limit} interview credits` : `One lifetime trial, up to ${plan?.trial_question_limit ?? "a limited number of"} questions`}</p>
      {plan?.plan === "FREE" && !plan.trial_available && <LinkButton href="/upgrade">Trial used — upgrade to Pro</LinkButton>}
      {history.length > 0 && <Card className="p-5 space-y-3"><h2 className="font-semibold">Recent sessions</h2>
        {history.slice(0, 10).map(item => <div key={item.session.interview_id} className="flex items-center justify-between gap-3">
          <span>{item.is_trial ? "Free trial" : "Pro interview"} — {item.session.question_count} questions</span>
          <Button variant="secondary" onClick={() => { setSession(item.session); loadQuestions(item.session.interview_id); localStorage.setItem(storageKey, item.session.interview_id); }}>Resume</Button>
        </div>)}
      </Card>}
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
            <Button size="lg" onClick={startInterview} disabled={isStarting}>
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
