import { authedRequest } from "@/lib/auth";
import type {
  InterviewAnswerResponse,
  InterviewEvaluationResponse,
  InterviewFullSessionResponse,
  InterviewQuestionResponse,
  InterviewResponse,
} from "@/lib/interviews";

export type FreeInterviewStatus = {
  available: boolean;
  trial_used: boolean;
  session_id: string | null;
  completed: boolean;
  resume_available: boolean;
  question_limit: number;
};

export const getFreeInterviewStatus = () =>
  authedRequest<FreeInterviewStatus>("/interviews/free-trial/status");

export const createFreeInterview = (role: string) =>
  authedRequest<InterviewResponse>("/interviews/free-trial", {
    method: "POST",
    body: JSON.stringify({ role }),
  });

export const getFreeInterview = (interviewId: string) =>
  authedRequest<InterviewFullSessionResponse>(`/interviews/free-trial/${interviewId}`);

export const generateFreeInterviewQuestion = (interviewId: string) =>
  authedRequest<InterviewQuestionResponse>(`/interviews/free-trial/${interviewId}/questions`, {
    method: "POST",
  });

export const submitFreeInterviewAnswer = (interviewId: string, questionId: string, answer: string) =>
  authedRequest<InterviewAnswerResponse>(`/interviews/free-trial/${interviewId}/answers`, {
    method: "POST",
    body: JSON.stringify({ question_id: questionId, answer_text: answer, source: "typed" }),
  });

export const evaluateFreeInterviewAnswer = (interviewId: string, answerId: string) =>
  authedRequest<InterviewEvaluationResponse>(
    `/interviews/free-trial/${interviewId}/answers/${answerId}/evaluate`,
    { method: "POST" },
  );
