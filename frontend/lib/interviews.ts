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

export type InterviewAnswer = {
  answer_id: string;
  interview_id: string;
  question_id: string;
  answer_text: string;
  source: "typed" | "voice";
  duration_seconds: number | null;
  submitted_at: string;
};

export type InterviewAnswerEvaluation = {
  evaluation_id: string;
  answer_id: string;
  overall_score: number;
  relevance_score: number;
  correctness_score: number;
  depth_score: number;
  clarity_score: number;
  evidence_score: number;
  strengths: string[];
  weaknesses: string[];
  missing_points: string[];
  feedback: string;
  evaluated_at: string;
  technical_correctness: number;
  relevance: number;
  reasoning: number;
  communication: number;
};

export type InterviewAnswerResponse = {
  success: boolean;
  data: InterviewAnswer | null;
  error: { code: string; message: string; details?: unknown } | null;
};

export type InterviewEvaluationResponse = {
  success: boolean;
  data: InterviewAnswerEvaluation | null;
  error: { code: string; message: string; details?: unknown } | null;
};

export function createInterview(applicationId: string | undefined, personality: InterviewPersonality, difficulty: InterviewDifficulty, requestId?: string) {
  return authedRequest<InterviewResponse>(applicationId ? "/interviews" : "/practice/interviews", {
    method: "POST",
    headers: requestId ? { "Idempotency-Key": requestId } : {},
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

export function submitInterviewAnswer(interviewId: string, questionId: string, answerText: string) {
  return authedRequest<InterviewAnswerResponse>(`/interviews/${interviewId}/answers`, {
    method: "POST",
    body: JSON.stringify({ question_id: questionId, answer_text: answerText, source: "typed" }),
  });
}

export function evaluateInterviewAnswer(interviewId: string, answerId: string) {
  return authedRequest<InterviewEvaluationResponse>(`/interviews/${interviewId}/answers/${answerId}/evaluate`, {
    method: "POST",
  });
}
