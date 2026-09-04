"use client";

import { useRef, useState, type DragEvent } from "react";
import { Alert, Badge, Button, Card, Spinner, Textarea, cx } from "@/components/ui";
import type { AnalyzeData, UploadData } from "@/lib/resumes";

type UploadFn = (file: File) => Promise<{ data: UploadData }>;
type AnalyzeFn = (resumeId: string, jd: { text?: string; file?: File }) => Promise<{ data: AnalyzeData }>;

const RESUME_ACCEPT =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const JD_ACCEPT = `${RESUME_ACCEPT},.txt,text/plain`;

/**
 * Resume upload plus job-description input, driven by whichever pair of API
 * functions the caller passes: the quick-scan pair for FREE accounts, the
 * application-scoped pair inside a workspace.
 */
export function ScanPanel({
  upload,
  analyze,
  initialJobDescription,
  initialResume,
  onAnalyzed,
}: {
  upload: UploadFn;
  analyze: AnalyzeFn;
  initialJobDescription?: string | null;
  initialResume?: { resume_id: string; version_number: number; skills: string[] } | null;
  onAnalyzed: (data: AnalyzeData) => void;
}) {
  const [resume, setResume] = useState(initialResume ?? null);
  const [fileName, setFileName] = useState("");
  const [jdText, setJdText] = useState(initialJobDescription ?? "");
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState<"upload" | "analyze" | null>(null);
  const [error, setError] = useState("");
  const resumeInput = useRef<HTMLInputElement>(null);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setError("");
    setBusy("upload");
    setFileName(file.name);
    try {
      const result = await upload(file);
      setResume({
        resume_id: result.data.resume_id,
        version_number: result.data.version_number,
        skills: result.data.parsed_data.skills,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to read that resume.");
      setFileName("");
    } finally {
      setBusy(null);
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    void handleFile(event.dataTransfer.files?.[0]);
  }

  async function runAnalysis() {
    if (!resume) return;
    if (!jdFile && !jdText.trim()) {
      setError("Add the job description as text or a file.");
      return;
    }
    setError("");
    setBusy("analyze");
    try {
      const result = await analyze(resume.resume_id, jdFile ? { file: jdFile } : { text: jdText });
      onAnalyzed(result.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to calculate the score.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {/* Step 1 — resume ------------------------------------------------- */}
      <Card className="p-6">
        <div className="flex items-center gap-2.5">
          <StepDot done={Boolean(resume)}>1</StepDot>
          <h2 className="text-[15px] font-semibold">Your resume</h2>
        </div>

        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cx(
            "mt-4 rounded-card border-2 border-dashed px-5 py-8 text-center transition-colors",
            dragging ? "border-brand-400 bg-brand-50" : "border-line-strong bg-surface-muted",
          )}
        >
          <p className="text-sm font-medium text-slate-700">Drop a PDF or DOCX here</p>
          <p className="mt-1 text-xs text-slate-500">or</p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="mt-2.5"
            disabled={busy !== null}
            onClick={() => resumeInput.current?.click()}
          >
            Choose a file
          </Button>
          <input
            ref={resumeInput}
            type="file"
            accept={RESUME_ACCEPT}
            className="sr-only"
            onChange={(event) => void handleFile(event.target.files?.[0])}
          />
          {fileName ? <p className="mt-3 truncate text-xs text-slate-500">{fileName}</p> : null}
          {busy === "upload" ? (
            <p className="mt-3">
              <Spinner label="Reading your resume…" />
            </p>
          ) : null}
        </div>

        {resume ? (
          <div className="mt-4 rounded-lg bg-surface-muted p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-slate-800">Version {resume.version_number} ready</p>
              <Badge tone="success">Parsed</Badge>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              {resume.skills.length} skill{resume.skills.length === 1 ? "" : "s"} detected. Your contact
              details are kept on the server and are never shown here.
            </p>
          </div>
        ) : null}
      </Card>

      {/* Step 2 — job description ---------------------------------------- */}
      <Card className="flex flex-col p-6">
        <div className="flex items-center gap-2.5">
          <StepDot done={Boolean(jdFile || jdText.trim())}>2</StepDot>
          <h2 className="text-[15px] font-semibold">The job description</h2>
        </div>

        <div className="mt-4 flex-1">
          <Textarea
            rows={7}
            value={jdText}
            disabled={Boolean(jdFile)}
            onChange={(event) => setJdText(event.target.value)}
            placeholder="Paste the full posting — requirements, qualifications and responsibilities."
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <label className="text-xs text-slate-500">
              <span className="mr-2">or upload a file</span>
              <input
                type="file"
                accept={JD_ACCEPT}
                className="text-xs file:mr-2 file:rounded-md file:border file:border-line file:bg-white file:px-2.5 file:py-1 file:text-xs file:font-medium"
                onChange={(event) => setJdFile(event.target.files?.[0] ?? null)}
              />
            </label>
            {jdFile ? (
              <Button variant="ghost" size="sm" onClick={() => setJdFile(null)}>
                Clear file
              </Button>
            ) : null}
          </div>
        </div>

        <Button
          size="lg"
          className="mt-5 w-full"
          disabled={!resume || busy !== null}
          onClick={runAnalysis}
        >
          {busy === "analyze" ? "Scoring…" : "Calculate ATS score"}
        </Button>
        {!resume ? <p className="mt-2 text-center text-xs text-slate-500">Upload a resume first.</p> : null}
      </Card>

      {error ? (
        <div className="md:col-span-2">
          <Alert>{error}</Alert>
        </div>
      ) : null}
    </div>
  );
}

function StepDot({ done, children }: { done: boolean; children: React.ReactNode }) {
  return (
    <span
      aria-hidden
      className={cx(
        "grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-bold",
        done ? "bg-emerald-100 text-emerald-700" : "bg-brand-50 text-brand-700",
      )}
    >
      {done ? "✓" : children}
    </span>
  );
}
