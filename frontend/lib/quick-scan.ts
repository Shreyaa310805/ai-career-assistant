import { authedRequest } from "@/lib/auth";
import type { AnalyzeData, Envelope, ResumeDetails } from "@/lib/resumes";

/**
 * The FREE-tier scanning surface. Same pipeline as the application-scoped
 * resume endpoints, against a scratch application the server manages, so no
 * application has to exist first.
 */
export type QuickScanUpload = {
  resume_id: string;
  application_id: string;
  version_number: number;
  parsed_data: ResumeDetails;
};

export type QuickScanLatest = {
  resume: {
    resume_id: string;
    version_number: number;
    created_at: string;
    parsed_data: ResumeDetails;
  } | null;
  report: {
    report_id: string;
    ats_score: number;
    match_score: number;
    matched_skills: string[];
    missing_skills: string[];
    improvement_suggestions: { category: string; action: string; impact: "High" | "Medium" | "Low" }[];
    ats_breakdown: Record<string, number> | null;
    match_breakdown: Record<string, number> | null;
    created_at: string;
  } | null;
};

export function uploadQuickResume(file: File) {
  const form = new FormData();
  form.append("file", file);
  return authedRequest<Envelope<QuickScanUpload>>("/quick-scan/resume", { method: "POST", body: form });
}

export function analyzeQuickScan(resumeId: string, jd: { text?: string; file?: File }) {
  const form = new FormData();
  form.append("resume_id", resumeId);
  if (jd.file) form.append("jd_file", jd.file);
  else form.append("jd_text", jd.text ?? "");
  return authedRequest<Envelope<AnalyzeData>>("/quick-scan/analyze", { method: "POST", body: form });
}

export const getLatestQuickScan = () => authedRequest<Envelope<QuickScanLatest>>("/quick-scan/latest");
