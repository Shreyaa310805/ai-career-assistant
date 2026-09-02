/**
 * TypeScript definitions for Module 1 (Resume & ATS) — Person 1.
 * Ready to copy into a Next.js frontend (e.g. types/resume.types.ts).
 *
 * These mirror the FastAPI Pydantic schemas in app/schemas.py exactly,
 * including the unified {success, data, error} envelope every endpoint
 * returns. Import ApiResponse<T> and wrap each endpoint's data shape.
 */

// ---------------------------------------------------------------------------
// Standard API envelope
// ---------------------------------------------------------------------------
export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: ApiError | null;
}

// ---------------------------------------------------------------------------
// Structured resume / JD data
// ---------------------------------------------------------------------------
export interface WorkHistoryItem {
  company: string;
  role: string;
  duration: string;
  bullets: string[];
}

export interface ParsedResumeData {
  candidate_name: string;
  email: string;
  phone: string;
  skills: string[];
  experience_years: number;
  work_history: WorkHistoryItem[];
  education: string[];
}

export interface ParsedJDData {
  role_title: string;
  required_skills: string[];
  preferred_skills: string[];
  min_experience_years: number;
  responsibilities: string[];
}

export type ImpactLevel = "High" | "Medium" | "Low";

export interface ImprovementSuggestion {
  category: string;
  action: string;
  impact: ImpactLevel;
}

// ---------------------------------------------------------------------------
// 1. POST /api/v1/resumes/upload
// ---------------------------------------------------------------------------
export interface UploadResumeRequest {
  file: File;
  application_id: string;
}

export interface UploadResumeData {
  resume_id: string;
  application_id: string;
  version_number: number;
  file_url: string;
  raw_text: string;
  parsed_data: ParsedResumeData;
}

export type UploadResumeResponse = ApiResponse<UploadResumeData>;

// ---------------------------------------------------------------------------
// 2. POST /api/v1/resumes/analyze
// Content-Type: multipart/form-data — the JD is uploaded as a file
// (.pdf / .docx / .txt), the same way a resume is, not as inline JSON text.
// ---------------------------------------------------------------------------
export interface AnalyzeResumeRequest {
  jd_file: File; // .pdf, .docx, or .txt
  application_id: string;
  resume_id: string;
}

export interface AnalyzeResumeData {
  report_id: string;
  application_id: string;
  resume_id: string;
  ats_score: number;
  match_score: number;
  matched_skills: string[];
  missing_skills: string[];
  improvement_suggestions: ImprovementSuggestion[];
}

export type AnalyzeResumeResponse = ApiResponse<AnalyzeResumeData>;

// ---------------------------------------------------------------------------
// 3. GET /api/v1/resumes/versions/{application_id}
// ---------------------------------------------------------------------------
export interface LatestAtsSummary {
  report_id: string;
  ats_score: number;
  match_score: number;
  created_at: string; // ISO-8601
}

export interface ResumeVersionSummary {
  resume_id: string;
  application_id: string;
  version_number: number;
  file_url: string;
  is_best_version: boolean;
  created_at: string; // ISO-8601
  parsed_data: ParsedResumeData;
  latest_ats_report: LatestAtsSummary | null;
}

export interface VersionListData {
  application_id: string;
  versions: ResumeVersionSummary[];
}

export type VersionListResponse = ApiResponse<VersionListData>;

// ---------------------------------------------------------------------------
// 4. POST /api/v1/resumes/compare
// ---------------------------------------------------------------------------
export interface CompareResumesRequest {
  resume_id_v1: string;
  resume_id_v2: string;
}

export interface VersionDiff {
  skills_gained: string[];
  skills_lost: string[];
  experience_years_delta: number;
  ats_score_delta: number | null;
  match_score_delta: number | null;
  education_gained: string[];
  education_lost: string[];
  work_history_count_delta: number;
}

export type RecommendedVersion = "v1" | "v2" | "tie";

export interface CompareResumesData {
  resume_v1: ResumeVersionSummary;
  resume_v2: ResumeVersionSummary;
  diff: VersionDiff;
  recommended_version: RecommendedVersion;
  recommendation_reason: string;
}

export type CompareResumesResponse = ApiResponse<CompareResumesData>;

// ---------------------------------------------------------------------------
// 5. PATCH /api/v1/resumes/select-best
// ---------------------------------------------------------------------------
export interface SelectBestRequest {
  application_id: string;
  best_resume_id: string;
}

export interface SelectBestData {
  application_id: string;
  best_resume_id: string;
  version_number: number;
  updated_versions: number;
}

export type SelectBestResponse = ApiResponse<SelectBestData>;

// ---------------------------------------------------------------------------
// Example fetch helpers (delete if your team uses a different HTTP client)
// ---------------------------------------------------------------------------
export async function uploadResume(
  baseUrl: string,
  req: UploadResumeRequest
): Promise<UploadResumeResponse> {
  const form = new FormData();
  form.append("file", req.file);
  form.append("application_id", req.application_id);
  const res = await fetch(`${baseUrl}/api/v1/resumes/upload`, {
    method: "POST",
    body: form,
  });
  return res.json();
}

export async function analyzeResume(
  baseUrl: string,
  req: AnalyzeResumeRequest
): Promise<AnalyzeResumeResponse> {
  const form = new FormData();
  form.append("jd_file", req.jd_file);
  form.append("application_id", req.application_id);
  form.append("resume_id", req.resume_id);
  const res = await fetch(`${baseUrl}/api/v1/resumes/analyze`, {
    method: "POST",
    body: form,
  });
  return res.json();
}

export async function getResumeVersions(
  baseUrl: string,
  applicationId: string
): Promise<VersionListResponse> {
  const res = await fetch(`${baseUrl}/api/v1/resumes/versions/${applicationId}`);
  return res.json();
}

export async function compareResumes(
  baseUrl: string,
  req: CompareResumesRequest
): Promise<CompareResumesResponse> {
  const res = await fetch(`${baseUrl}/api/v1/resumes/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return res.json();
}

export async function selectBestVersion(
  baseUrl: string,
  req: SelectBestRequest
): Promise<SelectBestResponse> {
  const res = await fetch(`${baseUrl}/api/v1/resumes/select-best`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return res.json();
}
