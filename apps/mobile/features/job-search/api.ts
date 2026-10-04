import { request } from "@/lib/api/client";

const BOOKMARK_MODEL_HEADERS = { "X-Recall-Job-Bookmarks": "separate-v1" } as const;
export type JobSearchFrequency = "daily" | "weekdays" | "weekly" | "monthly";
export type JobSearchWorkMode = "remote" | "hybrid" | "onsite";
export type JobSearchExperience = "internship" | "entry" | "mid" | "senior";
export type JobMatchStatus = "new" | "applied" | "interviewing" | "offer" | "rejected" | "hidden";
export type JobLocation = { country: string; region?: string | null; city?: string | null };
export type JobRunStatus = {
  id: string;
  state: "queued" | "running" | "completed" | "failed" | "limited" | "cancelled";
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  candidate_count: number;
  verified_count: number;
  qualifying_count: number;
  possible_count: number;
  new_match_count: number;
  partial: boolean;
  failure_reason: string | null;
  match_ids: string[];
};
export type JobSearchProfile = {
  id: string;
  revision?: number;
  target_roles: string[];
  skills: string[];
  location: string | null;
  country?: string | null;
  included_locations?: JobLocation[];
  excluded_locations?: JobLocation[];
  years_experience?: number | null;
  salary_currency?: string | null;
  salary_period?: "year" | "month" | "week" | "hour";
  needs_review?: boolean;
  suspension_reason?: string | null;
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
  company_logo_url: string | null;
  location: string | null;
  work_mode: JobSearchWorkMode | null;
  salary: string | null;
  experience: string | null;
  match_score: number | null;
  match_kind?: "qualifying" | "possible";
  fit_label?: "Strong fit" | "Potential fit" | "Needs review";
  outdated?: boolean;
  pro_required?: boolean;
  checked_at?: string | null;
  assessment?: Record<string, unknown>;
  url: string;
  source: string | null;
  posted_at: string | null;
  summary: string | null;
  required_skills: string[];
  match_reasons: string[];
  gap: string | null;
  found_at: string;
  status: JobMatchStatus;
  is_saved: boolean;
  notes: string | null;
};
export type JobSearchDashboard = {
  profile: JobSearchProfile | null;
  matches: JobMatch[];
  latest_run?: JobRunStatus | null;
  pro_required?: boolean;
  premium_enabled?: boolean;
  manual_remaining?: number;
  cooldown_until?: string | null;
  next_offset?: number | null;
};
export type JobSearchInput = {
  target_roles: string[];
  skills: string[];
  location: string | null;
  country?: string | null;
  included_locations?: JobLocation[];
  excluded_locations?: JobLocation[];
  years_experience?: number | null;
  salary_currency?: string | null;
  salary_period?: "year" | "month" | "week" | "hour";
  expected_revision?: number | null;
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
export type JobMatchView = "new" | "all" | "applied";

export const jobSearchApi = {
  getJobSearch: (token: string, includeMatches = true) => request<JobSearchDashboard>(`/job-search${includeMatches ? "" : "?include_matches=false"}`, token, { headers: BOOKMARK_MODEL_HEADERS }),
  getJobMatch: (token: string, id: string) => request<JobMatch>(`/job-search/matches/${id}`, token, { headers: BOOKMARK_MODEL_HEADERS }),
  getJobMatches: (token: string, offset = 0, runId?: string, view?: JobMatchView) => request<{ matches: JobMatch[]; next_offset: number | null }>(`/job-search/matches?offset=${offset}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}${view ? `&view=${view}` : ""}`, token, { headers: BOOKMARK_MODEL_HEADERS }),
  getJobRun: (token: string, id: string) => request<JobRunStatus>(`/job-search/runs/${id}`, token),
  saveJobSearch: (token: string, input: JobSearchInput) => request<JobSearchDashboard>("/job-search", token, { method: "PUT", headers: BOOKMARK_MODEL_HEADERS, body: JSON.stringify(input) }),
  patchJobSearch: (token: string, input: Partial<JobSearchInput>) => request<JobSearchDashboard>("/job-search", token, { method: "PATCH", headers: BOOKMARK_MODEL_HEADERS, body: JSON.stringify(input) }),
  setJobSearchStatus: (token: string, status: "active" | "paused") => request<JobSearchDashboard>("/job-search/status", token, { method: "PATCH", headers: BOOKMARK_MODEL_HEADERS, body: JSON.stringify({ status }) }),
  setJobMatchStatus: (token: string, id: string, status: JobMatchStatus, notes?: string | null) => request<JobSearchDashboard>(`/job-search/matches/${id}`, token, { method: "PATCH", headers: BOOKMARK_MODEL_HEADERS, body: JSON.stringify(notes === undefined ? { status } : { status, notes }) }),
  setJobMatchSaved: (token: string, id: string, isSaved: boolean) => request<JobSearchDashboard>(`/job-search/matches/${id}`, token, { method: "PATCH", headers: BOOKMARK_MODEL_HEADERS, body: JSON.stringify({ is_saved: isSaved }) }),
  generateCoverLetter: (token: string, id: string) => request<{ cover_letter: string }>(`/job-search/matches/${id}/cover-letter`, token, { method: "POST", headers: BOOKMARK_MODEL_HEADERS }),
  runJobSearch: (token: string, requestKey: string) => request<{ queued: boolean; run_id: string; state: JobRunStatus["state"] }>("/job-search/run", token, { method: "POST", headers: { ...BOOKMARK_MODEL_HEADERS, "Idempotency-Key": requestKey } }),
  deleteJobSearch: (token: string) => request<void>("/job-search", token, { method: "DELETE", headers: BOOKMARK_MODEL_HEADERS }),
};
