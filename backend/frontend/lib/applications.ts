import { authedRequest } from "@/lib/auth";

export type Status = "SAVED" | "APPLIED" | "INTERVIEWING" | "SELECTED" | "OFFER" | "OFFER_DECLINED" | "REJECTED";

export const STATUS_ORDER: Status[] = [
  "SAVED",
  "APPLIED",
  "INTERVIEWING",
  "SELECTED",
  "OFFER",
  "OFFER_DECLINED",
  "REJECTED",
];

export const STATUS_LABEL: Record<Status, string> = {
  SAVED: "Saved",
  APPLIED: "Applied",
  INTERVIEWING: "Interviewing",
  SELECTED: "Selected",
  OFFER: "Offer",
  OFFER_DECLINED: "Offer declined",
  REJECTED: "Rejected",
};

export type Application = {
  id: string;
  company: string;
  role: string;
  status: Status;
  location: string | null;
  job_url: string | null;
  job_description: string | null;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Summary = {
  total: number;
  saved: number;
  applied: number;
  interviewing: number;
  selected: number;
  offer: number;
  offer_declined: number;
  rejected: number;
  recent_applications: Application[];
};

export type ApplicationInput = Omit<Application, "id" | "created_at" | "updated_at">;

export const getSummary = () => authedRequest<Summary>("/dashboard/summary");
export const getApplications = () => authedRequest<Application[]>("/applications");
export const getApplication = (id: string) => authedRequest<Application>(`/applications/${id}`);

export const createApplication = (input: Partial<ApplicationInput>) =>
  authedRequest<Application>("/applications", { method: "POST", body: JSON.stringify(input) });

export const updateApplication = (id: string, input: Partial<ApplicationInput>) =>
  authedRequest<Application>(`/applications/${id}`, { method: "PATCH", body: JSON.stringify(input) });

export const deleteApplication = (id: string) =>
  authedRequest<void>(`/applications/${id}`, { method: "DELETE" });
