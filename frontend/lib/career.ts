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

const API_BASE_URL = process.env.NEXT_PUBLIC_CAREER_API_URL ?? "http://localhost:8000/api/v1/career";

export async function getCareerRoadmap(applicationId: string, token: string, signal?: AbortSignal): Promise<CareerRoadmap> {
  const response = await fetch(`${API_BASE_URL}/roadmap/${applicationId}`, { signal, headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Unable to load career roadmap");
  }
  return response.json() as Promise<CareerRoadmap>;
}

export async function simulateWhatIf(applicationId: string, skill: string, targetLevel: number, token: string): Promise<WhatIfResult> {
  const response = await fetch(`${API_BASE_URL}/what-if/${applicationId}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ skill, target_level: targetLevel }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Unable to estimate the match improvement");
  }
  return response.json() as Promise<WhatIfResult>;
}
