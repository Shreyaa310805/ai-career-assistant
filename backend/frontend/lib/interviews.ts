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

export function createInterview(applicationId: string, personality: InterviewPersonality, difficulty: InterviewDifficulty) {
  return authedRequest<InterviewResponse>("/interviews", {
    method: "POST",
    body: JSON.stringify({ application_id: applicationId, personality, difficulty }),
  });
}

export const getInterview = (interviewId: string) => authedRequest<InterviewResponse>(`/interviews/${interviewId}`);
