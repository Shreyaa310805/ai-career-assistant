import { authedRequest, getToken } from "@/lib/auth";

type Confidence = { status: string; score: number | null; observations_count: number; basis: string };
type Question = {
  interview_id: string; question_id: string; answer_id: string; question_number: number; question: string;
  topic: string; expected_skills: string[]; answer_modality: string; answer_text: string;
  scores: Record<string, number | null>; strengths: string[]; weaknesses: string[]; missing_points: string[];
  feedback: string; confidence_rationale: string;
  visual_analysis: { composure: number; observations: string[]; common_expressions: string[] } | null;
};
export type ApplicationInterviewReport = {
  application_id: string; company: string; role: string; generated_at: string; completed_session_count: number;
  total_questions_attempted: number; total_questions_evaluated: number; metrics: Record<string, number | null>;
  verbal_confidence: Confidence; visual_confidence: Confidence; readiness: string; summary: string;
  date_range: { from: string | null; to: string | null };
  sessions: { interview_id: string; personality: string; difficulty: string; mode: string; overall_score: number | null;
    questions_attempted: number; completed_at: string | null; strengths: string[]; areas_to_improve: string[] }[];
  strengths: string[]; areas_to_improve: string[]; recommended_focus_areas: string[];
  skill_evidence: { skill: string; status: string; score: number | null; evidence: { interview_id: string; question_id: string; reason: string }[] }[];
  per_question_analysis: Question[];
};

export const getApplicationInterviewReport = (id: string) => authedRequest<{ success: boolean; data: ApplicationInterviewReport }>(`/applications/${id}/interview-report`);

export type SessionInterviewReport = {
  readiness: string; confidence_score: number | null; questions_attempted: number; questions_evaluated: number;
  verbal_confidence: Confidence; visual_confidence: Confidence; per_question_analysis: Question[];
};
export const getSessionInterviewReport = (id: string) => authedRequest<{ success: boolean; data: SessionInterviewReport }>(`/interviews/${id}/report`);

export async function downloadInterviewReport(id: string) {
  const token = getToken();
  if (!token) throw new Error("Please sign in again.");
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/applications/${id}/interview-report/pdf`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error("Unable to download the report. Check your access and try again.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url; link.download = `SkillSync-interview-report-${id}.pdf`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
