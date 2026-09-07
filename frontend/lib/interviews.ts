import { authedRequest } from "@/lib/auth";

export type InterviewPersonality = "technical" | "friendly" | "strict" | "behavioral" | "mixed";
export type InterviewDifficulty = "easy" | "medium" | "hard";

export type InterviewSession = {
  interview_id: string;
  application_id: string;
  personality: InterviewPersonality;
  difficulty: InterviewDifficulty;
  status: "created";
  question_count: number;
  started_at: string | null;
};

export type InterviewResponse = {
  success: boolean;
  data: InterviewSession | null;
  error: { code: string; message: string; details?: unknown } | null;
};

export type InterviewQuestion = {
  question_id: string;
  interview_id: string;
  question_number: number;
  question: string;
  topic: string;
  question_type: string;
  difficulty: InterviewDifficulty;
  expected_skills: string[];
  reason: string;
};

export type InterviewQuestionResponse = {
  success: boolean;
  data: InterviewQuestion | null;
  error: { code: string; message: string; details?: unknown } | null;
};

export function createInterview(applicationId: string, personality: InterviewPersonality, difficulty: InterviewDifficulty) {
  return authedRequest<InterviewResponse>("/interviews", {
    method: "POST",
    body: JSON.stringify({ application_id: applicationId, personality, difficulty }),
  });
}

export const getInterview = (interviewId: string) => authedRequest<InterviewResponse>(`/interviews/${interviewId}`);

export function generateInterviewQuestion(interviewId: string, mode: "standard" | "adaptive" = "standard") {
  return authedRequest<InterviewQuestionResponse>(`/interviews/${interviewId}/questions`, {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}
