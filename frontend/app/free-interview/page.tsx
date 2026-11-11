"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Alert, Button, Card, Field, LinkButton, SectionHeading, Skeleton } from "@/components/ui";
import { getToken } from "@/lib/auth";
import { createFreeInterview, getFreeInterviewStatus, type FreeInterviewStatus } from "@/lib/free-interview";

export default function FreeInterviewStartPage() {
  const router = useRouter();
  const [status, setStatus] = useState<FreeInterviewStatus | null>(null);
  const [role, setRole] = useState("Software Engineer");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    getFreeInterviewStatus()
      .then(setStatus)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load free interview status."))
      .finally(() => setLoading(false));
  }, [router]);

  async function start() {
    setBusy(true);
    setError("");
    try {
      const result = await createFreeInterview(role);
      if (!result.success || !result.data) {
        throw new Error(result.error?.message ?? "Unable to start your free interview.");
      }
      router.push(`/free-interview/${result.data.interview_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start your free interview.");
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-3xl px-5 py-8 sm:px-8">
        <SectionHeading
          eyebrow="Free plan · text practice"
          title="Try a three-question interview"
          description="Practice answering three role-focused questions in text. You’ll get feedback on each answer."
        />

        <Card className="mt-8 p-6 sm:p-8">
          {loading ? (
            <Skeleton className="h-48 w-full" />
          ) : error ? (
            <div className="space-y-5">
              <Alert>{error}</Alert>
              <LinkButton href="/dashboard" variant="secondary">Back to dashboard</LinkButton>
            </div>
          ) : status?.session_id ? (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">Continue your free interview</h2>
              <p className="text-sm leading-6 text-slate-600">Your three-question session is in progress. Continue where you left off.</p>
              <LinkButton href={`/free-interview/${status.session_id}`}>Continue interview</LinkButton>
            </div>
          ) : status?.trial_used ? (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">Your free interview is used</h2>
              <p className="text-sm leading-6 text-slate-600">Upgrade to Premium for more interview practice, reports, and preparation tools.</p>
              <LinkButton href="/upgrade">Explore Premium</LinkButton>
            </div>
          ) : !status?.resume_available ? (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">Upload your resume first</h2>
              <p className="text-sm leading-6 text-slate-600">The free interview uses your resume to tailor its questions. Upload it in the ATS checker, then come back here.</p>
              <LinkButton href="/dashboard">Go to ATS checker</LinkButton>
            </div>
          ) : (
            <div className="space-y-5">
              <div className="rounded-lg bg-surface-muted p-4 text-sm leading-6 text-slate-600">
                This is one free interview with {status.question_limit} text questions. Audio, video, and additional sessions are part of Premium.
              </div>
              <Field label="Role you’re preparing for" hint="Questions will use this role and the resume you uploaded for ATS scoring.">
                <input
                  className="field"
                  value={role}
                  onChange={(event) => setRole(event.target.value)}
                  maxLength={120}
                  required
                />
              </Field>
              {error ? <Alert>{error}</Alert> : null}
              <div className="flex flex-wrap gap-3">
                <Button onClick={start} disabled={busy || role.trim().length < 2}>
                  {busy ? "Starting interview…" : "Start free interview"}
                </Button>
                <LinkButton href="/upgrade" variant="secondary">See Premium</LinkButton>
              </div>
            </div>
          )}
        </Card>
      </main>
    </AppShell>
  );
}
