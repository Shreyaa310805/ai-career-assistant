import { authedRequest } from "@/lib/auth";

export type InterviewPersonality = "technical" | "friendly" | "strict" | "behavioral" | "mixed";
export type InterviewDifficulty = "easy" | "medium" | "hard";
export type InterviewStatus = "created" | "in_progress" | "completed";
export type InterviewMode = "text" | "audio" | "video";

export const interviewSessionPath = (interviewId: string, mode: InterviewMode) =>
  mode === "video" ? `/video-interview/${interviewId}` : `/interview-session/${interviewId}`;

export type VisualAnalysis = {
  visual_score: number;
  frames_analyzed: number;
  face_visible_rate: number;
  eye_contact_rate: number;
  engagement: number;
  attentiveness: number;
  composure: number;
  presentation: number;
  common_expressions: string[];
  observations: string[];
};

export const MAX_INTERVIEW_QUESTIONS = 6;

export type InterviewSession = {
  interview_id: string;
  application_id: string;
  personality: InterviewPersonality;
  difficulty: InterviewDifficulty;
  status: InterviewStatus;
  question_count: number;
  question_target: number;
  mode: InterviewMode;
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
  confidence_score: number;
  confidence_rationale: string;
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

export type InterviewSummary = {
  interview_id: string;
  application_id: string;
  personality: InterviewPersonality;
  difficulty: InterviewDifficulty;
  status: InterviewStatus;
  question_count: number;
  question_target: number;
  answered_count: number;
  average_score: number | null;
  average_confidence: number | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  recommendation: string | null;
  mode: InterviewMode;
  visual_score: number | null;
};

export type InterviewHistory = {
  items: InterviewSummary[];
  total: number;
  page: number;
  page_size: number;
};

export type InterviewHistoryResponse = {
  success: boolean;
  data: InterviewHistory | null;
  error: { code: string; message: string; details?: unknown } | null;
};

export type InterviewQuestionWithAnswer = {
  question: InterviewQuestion;
  answer: InterviewAnswer | null;
  evaluation: InterviewAnswerEvaluation | null;
};

export type InterviewFullSession = {
  interview_id: string;
  application_id: string;
  personality: InterviewPersonality;
  difficulty: InterviewDifficulty;
  status: InterviewStatus;
  question_target: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  summary: string | null;
  recommendation: string | null;
  average_score: number | null;
  average_confidence: number | null;
  mode: InterviewMode;
  visual_analysis: VisualAnalysis | null;
  items: InterviewQuestionWithAnswer[];
};

export type InterviewFullSessionResponse = {
  success: boolean;
  data: InterviewFullSession | null;
  error: { code: string; message: string; details?: unknown } | null;
};

export type CompleteInterviewResult = {
  interview_id: string;
  status: InterviewStatus;
  completed_at: string;
  question_count: number;
  answered_count: number;
  average_score: number | null;
  average_confidence: number | null;
  summary: string;
  recommendation: string;
  mode: InterviewMode;
  visual_analysis: VisualAnalysis | null;
};

export type CompleteInterviewResponse = {
  success: boolean;
  data: CompleteInterviewResult | null;
  error: { code: string; message: string; details?: unknown } | null;
};

export function createInterview(
  applicationId: string,
  personality: InterviewPersonality,
  difficulty: InterviewDifficulty,
  questionTarget: number,
  mode: InterviewMode,
) {
  return authedRequest<InterviewResponse>("/interviews", {
    method: "POST",
    body: JSON.stringify({ application_id: applicationId, personality, difficulty, question_target: questionTarget, mode }),
  });
}

export const deleteInterview = (interviewId: string) =>
  authedRequest<{ success: boolean; data: null; error: { code: string; message: string } | null }>(
    `/interviews/${interviewId}`,
    { method: "DELETE" },
  );

export const getInterview = (interviewId: string) => authedRequest<InterviewResponse>(`/interviews/${interviewId}`);

export function generateInterviewQuestion(interviewId: string) {
  return authedRequest<InterviewQuestionResponse>(`/interviews/${interviewId}/questions`, {
    method: "POST",
  });
}

export function submitInterviewAnswer(interviewId: string, questionId: string, answerText: string, durationSeconds?: number) {
  return authedRequest<InterviewAnswerResponse>(`/interviews/${interviewId}/answers`, {
    method: "POST",
    body: JSON.stringify({
      question_id: questionId,
      answer_text: answerText,
      source: "typed",
      duration_seconds: durationSeconds ?? null,
    }),
  });
}

export function evaluateInterviewAnswer(interviewId: string, answerId: string) {
  return authedRequest<InterviewEvaluationResponse>(`/interviews/${interviewId}/answers/${answerId}/evaluate`, {
    method: "POST",
  });
}

export function listInterviews(applicationId?: string, page = 1, pageSize = 10) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (applicationId) params.set("application_id", applicationId);
  return authedRequest<InterviewHistoryResponse>(`/interviews?${params.toString()}`);
}

export const getInterviewFull = (interviewId: string) =>
  authedRequest<InterviewFullSessionResponse>(`/interviews/${interviewId}/full`);

export const completeInterview = (interviewId: string) =>
  authedRequest<CompleteInterviewResponse>(`/interviews/${interviewId}/complete`, { method: "POST" });

export function submitInterviewAudio(interviewId: string, questionId: string, audio: Blob, duration: number) {
  const body = new FormData();
  body.append("audio", audio, "recording");
  body.append("duration_seconds", String(duration));
  return authedRequest<InterviewAnswerResponse>(`/interviews/${interviewId}/questions/${questionId}/audio-answer`, {
    method: "POST", body,
  });
}

export type VisualFrameResponse = {
  success: boolean;
  data: { frame_id: string; interview_id: string; frames_analyzed: number } | null;
  error: { code: string; message: string; details?: unknown } | null;
};

export function submitVisualFrame(interviewId: string, frame: Blob, questionId?: string) {
  const body = new FormData();
  body.append("frame", frame, "frame.jpg");
  if (questionId) body.append("question_id", questionId);
  return authedRequest<VisualFrameResponse>(`/interviews/${interviewId}/visual-frames`, { method: "POST", body });
}
