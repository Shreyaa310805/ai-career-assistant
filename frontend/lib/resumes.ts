import { authedRequest } from "@/lib/auth";

export type ResumeDetails = { skills: string[]; experience_years: number; work_history: { company: string; role: string; duration: string; bullets: string[] }[]; education: string[] };
export type JobDescriptionDetails = { role_title: string; required_skills: string[]; preferred_skills: string[]; min_experience_years: number; responsibilities: string[] };
export type UploadResumeResult = { success: boolean; data: { resume_id: string; application_id: string; version_number: number; parsed_data: ResumeDetails }; error: null | { message: string } };
export type AnalyzeResumeResult = { success: boolean; data: { ats_score: number; match_score: number; jd_details: JobDescriptionDetails }; error: null | { message: string } };

export const uploadResume = (applicationId: string, file: File) => {
  const form = new FormData(); form.append("application_id", applicationId); form.append("file", file);
  return authedRequest<UploadResumeResult>("/resumes/upload", { method: "POST", body: form });
};
export const analyzeResume = (applicationId: string, resumeId: string, jdText: string) => {
  const form = new FormData(); form.append("application_id", applicationId); form.append("resume_id", resumeId); form.append("jd_text", jdText);
  return authedRequest<AnalyzeResumeResult>("/resumes/analyze", { method: "POST", body: form });
};
