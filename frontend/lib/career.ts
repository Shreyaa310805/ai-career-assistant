import { authedRequest } from "@/lib/auth";

export type Priority = "High" | "Medium" | "Low";

export type CareerRoadmap = {
  application_id: string;
  company: string;
  role: string;
  current_match_score: number;
  skill_gap: {
    matched_skills: string[];
    missing_skills: string[];
    extra_skills: string[];
    skill_gap_count: number;
  };
  prioritized_skills: Array<{
    skill: string;
    priority: Priority;
    priority_score: number;
    reason: string;
  }>;
  recommendations: Array<{
    skill: string;
    priority: Priority;
    resources: Array<{
      title: string;
      provider: string;
      difficulty: string;
      type: string;
      url: string;
    }>;
  }>;
};

export type WhatIfResult = {
  application_id: string;
  skill: string;
  current_level: number;
  target_level: number;
  current_match_score: number;
  estimated_match_score: number;
  estimated_improvement: number;
  impact: Priority;
  message: string;
};

/* -------------------------------------------------------------------------- */
/* Career intelligence lives on the main API, behind the same bearer token as  */
/* every other client. There is no separate service and no separate base URL.  */
/* -------------------------------------------------------------------------- */

export const getCareerRoadmap = (applicationId: string, signal?: AbortSignal) =>
  authedRequest<CareerRoadmap>(`/career/roadmap/${applicationId}`, { signal });

export const simulateWhatIf = (applicationId: string, skill: string, targetLevel: number) =>
  authedRequest<WhatIfResult>(`/career/what-if/${applicationId}`, {
    method: "POST",
    body: JSON.stringify({ skill, target_level: targetLevel }),
  });
