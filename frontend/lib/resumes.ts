import { authedRequest } from "@/lib/auth";

/** The {success, data, error} envelope used by /resumes and /quick-scan. */
export type Envelope<T> = {
  success: boolean;
  data: T;
  error: { code: string; message: string } | null;
};

export type WorkHistoryItem = { company: string; role: string; duration: string; bullets: string[] };

/** The only resume projection the API returns. Contact details stay server-side. */
export type ResumeDetails = {
  skills: string[];
  experience_years: number;
  work_history: WorkHistoryItem[];
  education: string[];
};

export type JobDescriptionDetails = {
  role_title: string;
  required_skills: string[];
  preferred_skills: string[];
  min_experience_years: number;
  responsibilities: string[];
};

export type ImprovementSuggestion = {
  category: string;
  action: string;
  impact: "High" | "Medium" | "Low";
};

export type UploadData = {
  resume_id: string;
  application_id: string;
  version_number: number;
  parsed_data: ResumeDetails;
};

export type AnalyzeData = {
  report_id: string;
  application_id: string;
  resume_id: string;
  ats_score: number;
  match_score: number;
  matched_skills: string[];
  missing_skills: string[];
  improvement_suggestions: ImprovementSuggestion[];
  jd_details: JobDescriptionDetails;
  /** Optional: absent on reports created before breakdowns were persisted. */
  ats_breakdown: Record<string, number> | null;
  match_breakdown: Record<string, number> | null;
};

export type LatestAtsSummary = {
  report_id: string;
  ats_score: number;
  match_score: number;
  created_at: string;
  ats_breakdown: Record<string, number> | null;
  match_breakdown: Record<string, number> | null;
};

export type ResumeVersionSummary = {
  resume_id: string;
  application_id: string;
  version_number: number;
  /** Opaque `resume://<id>` reference, never a storage path. */
  file_url: string;
  is_best_version: boolean;
  created_at: string;
  parsed_data: ResumeDetails;
  latest_ats_report: LatestAtsSummary | null;
};

export type VersionDiff = {
  skills_gained: string[];
  skills_lost: string[];
  experience_years_delta: number;
  ats_score_delta: number | null;
  match_score_delta: number | null;
  education_gained: string[];
  education_lost: string[];
  work_history_count_delta: number;
};

export type CompareData = {
  resume_v1: ResumeVersionSummary;
  resume_v2: ResumeVersionSummary;
  diff: VersionDiff;
  recommended_version: "v1" | "v2" | "tie";
  recommendation_reason: string;
};

/* -------------------------------------------------------------------------- */

export function uploadResume(applicationId: string, file: File) {
  const form = new FormData();
  form.append("application_id", applicationId);
  form.append("file", file);
  return authedRequest<Envelope<UploadData>>("/resumes/upload", { method: "POST", body: form });
}

export function analyzeResume(
  applicationId: string,
  resumeId: string,
  jd: { text?: string; file?: File },
) {
  const form = new FormData();
  form.append("application_id", applicationId);
  form.append("resume_id", resumeId);
  if (jd.file) form.append("jd_file", jd.file);
  else form.append("jd_text", jd.text ?? "");
  return authedRequest<Envelope<AnalyzeData>>("/resumes/analyze", { method: "POST", body: form });
}

export const getVersions = (applicationId: string) =>
  authedRequest<Envelope<{ application_id: string; versions: ResumeVersionSummary[] }>>(
    `/resumes/versions/${applicationId}`,
  );

export const compareResumes = (resumeIdV1: string, resumeIdV2: string) =>
  authedRequest<Envelope<CompareData>>("/resumes/compare", {
    method: "POST",
    body: JSON.stringify({ resume_id_v1: resumeIdV1, resume_id_v2: resumeIdV2 }),
  });

export const selectBestVersion = (applicationId: string, bestResumeId: string) =>
  authedRequest<Envelope<{ application_id: string; best_resume_id: string; version_number: number }>>(
    "/resumes/select-best",
    { method: "PATCH", body: JSON.stringify({ application_id: applicationId, best_resume_id: bestResumeId }) },
  );
