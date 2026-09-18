import { request } from "@/lib/api/client";

export type JobSearchFrequency = "daily" | "weekdays" | "weekly" | "monthly";
export type JobSearchWorkMode = "remote" | "hybrid" | "onsite";
export type JobSearchExperience = "internship" | "entry" | "mid" | "senior";
export type JobMatchStatus = "new" | "saved" | "applied" | "hidden";

export type JobSearchProfile = {
  id: string;
  target_roles: string[];
  skills: string[];
  location: string | null;
  work_modes: JobSearchWorkMode[];
  experience_levels: JobSearchExperience[];
  salary_min: number | null;
  requires_sponsorship: boolean | null;
  excluded_companies: string[];
  background: string | null;
  resume_attachment_id: string | null;
  resume_filename: string | null;
  result_count: 5 | 10 | 15;
  frequency: JobSearchFrequency;
  next_run_at: string;
  status: "active" | "paused" | "completed";
  last_run_at: string | null;
  last_run_status: "ok" | "skipped_quota" | "error" | null;
  created_at: string;
  updated_at: string;
};

export type JobMatch = {
  id: string;
  title: string;
  company: string;
  location: string | null;
  work_mode: JobSearchWorkMode | null;
  salary: string | null;
  url: string;
  source: string | null;
  posted_at: string | null;
  summary: string | null;
  match_reasons: string[];
  gap: string | null;
  found_at: string;
  status: JobMatchStatus;
};

export type JobSearchDashboard = {
  profile: JobSearchProfile | null;
  matches: JobMatch[];
};

export type JobSearchInput = {
  target_roles: string[];
  skills: string[];
  location: string | null;
  work_modes: JobSearchWorkMode[];
  experience_levels: JobSearchExperience[];
  salary_min: number | null;
  requires_sponsorship: boolean | null;
  excluded_companies: string[];
  background: string | null;
  resume_attachment_id: string | null;
  result_count: 5 | 10 | 15;
  frequency: JobSearchFrequency;
  next_run_at: string;
};

export const jobSearchApi = {
  getJobSearch: (token: string) => request<JobSearchDashboard>("/job-search", token),
  saveJobSearch: (token: string, input: JobSearchInput) =>
    request<JobSearchDashboard>("/job-search", token, {
      method: "PUT",
      body: JSON.stringify(input),
    }),
  setJobSearchStatus: (token: string, status: "active" | "paused") =>
    request<JobSearchDashboard>("/job-search/status", token, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  setJobMatchStatus: (token: string, id: string, status: JobMatchStatus) =>
    request<JobSearchDashboard>(`/job-search/matches/${id}`, token, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  runJobSearchNow: (token: string) =>
    request<JobSearchDashboard>("/job-search/run-now", token, { method: "POST" }),
  deleteJobSearch: (token: string) =>
    request<void>("/job-search", token, { method: "DELETE" }),
};
