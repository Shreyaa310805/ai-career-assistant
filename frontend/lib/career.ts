export type Priority = "High" | "Medium" | "Low";

export type CareerRoadmap = {
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

const API_BASE_URL = process.env.NEXT_PUBLIC_CAREER_API_URL ?? "http://127.0.0.1:8000/api/v1/career";

export async function getCareerRoadmap(signal?: AbortSignal): Promise<CareerRoadmap> {
  const response = await fetch(`${API_BASE_URL}/roadmap/app_123`, { signal });
  if (!response.ok) throw new Error("Unable to load career roadmap");
  return response.json() as Promise<CareerRoadmap>;
}
