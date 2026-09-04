/**
 * Integration types for the Resume & ATS module.
 *
 * These mirror what the API actually returns. Note in particular that the
 * server does NOT return `candidate_name`, `email`, `phone`, `raw_text`, or a
 * storage path: identity data extracted from a resume stays server-side, and
 * `file_url` is an opaque `resume://<resume_id>` reference. See backend/API.md.
 *
 * The runtime client lives in `lib/resumes.ts` and re-exports the same shapes;
 * this file exists as a standalone drop-in for other frontends.
 */

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

/* -------------------------------------------------------------------------- */
/* Structured resume / JD data                                                */
/* -------------------------------------------------------------------------- */

export interface WorkHistoryItem {
  company: string;
  role: string;
  duration: string;
  bullets: string[];
}

/** The only resume projection any endpoint returns. */
export interface ResumeDetails {
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

/* -------------------------------------------------------------------------- */
/* POST /api/v1/resumes/upload  (multipart: file, application_id)             */
/* -------------------------------------------------------------------------- */

export interface UploadResumeData {
  resume_id: string;
  application_id: string;
  version_number: number;
  parsed_data: ResumeDetails;
}

export type UploadResumeResponse = ApiResponse<UploadResumeData>;

/* -------------------------------------------------------------------------- */
/* POST /api/v1/resumes/analyze                                               */
/* multipart: application_id, resume_id, and one of jd_file | jd_text         */
/* -------------------------------------------------------------------------- */

export interface AnalyzeResumeData {
  report_id: string;
  application_id: string;
  resume_id: string;
  /** Resume quality blended with keyword coverage against this specific job description. */
  ats_score: number;
  /** Fit against this specific job description. */
  match_score: number;
  matched_skills: string[];
  missing_skills: string[];
  improvement_suggestions: ImprovementSuggestion[];
  jd_details: ParsedJDData;
  /** Optional and additive: null on reports created before breakdowns existed. */
  ats_breakdown: Record<string, number> | null;
  match_breakdown: Record<string, number> | null;
}

export type AnalyzeResumeResponse = ApiResponse<AnalyzeResumeData>;

/* -------------------------------------------------------------------------- */
/* GET /api/v1/resumes/versions/{application_id}                              */
/* -------------------------------------------------------------------------- */

export interface LatestAtsSummary {
  report_id: string;
  ats_score: number;
  match_score: number;
  created_at: string;
  ats_breakdown: Record<string, number> | null;
  match_breakdown: Record<string, number> | null;
}

export interface ResumeVersionSummary {
  resume_id: string;
  application_id: string;
  version_number: number;
  /** Opaque reference (`resume://<resume_id>`), never a storage path. */
  file_url: string;
  is_best_version: boolean;
  created_at: string;
  parsed_data: ResumeDetails;
  latest_ats_report: LatestAtsSummary | null;
}

export interface VersionListData {
  application_id: string;
  versions: ResumeVersionSummary[];
}

export type VersionListResponse = ApiResponse<VersionListData>;

/* -------------------------------------------------------------------------- */
/* POST /api/v1/resumes/compare                                               */
/* -------------------------------------------------------------------------- */

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

/* -------------------------------------------------------------------------- */
/* PATCH /api/v1/resumes/select-best                                          */
/* -------------------------------------------------------------------------- */

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

/* -------------------------------------------------------------------------- */
/* Quick scan — the same pipeline without an application (FREE tier)          */
/* -------------------------------------------------------------------------- */

export interface QuickScanLatestData {
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
    improvement_suggestions: ImprovementSuggestion[];
    ats_breakdown: Record<string, number> | null;
    match_breakdown: Record<string, number> | null;
    created_at: string;
  } | null;
}

export type QuickScanLatestResponse = ApiResponse<QuickScanLatestData>;
