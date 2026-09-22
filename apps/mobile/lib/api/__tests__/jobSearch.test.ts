import { jobSearchApi, type JobSearchInput } from "@/lib/api/jobSearch";
import { request } from "@/lib/api/client";

jest.mock("@/lib/api/client", () => ({ request: jest.fn() }));

beforeEach(() => jest.resetAllMocks());

const bookmarkHeaders = { "X-Recall-Job-Bookmarks": "separate-v1" };

const input: JobSearchInput = {
  target_roles: ["Backend Engineer"],
  skills: ["Python", "FastAPI"],
  location: "Remote in the United States",
  work_modes: ["remote"],
  experience_levels: ["entry"],
  salary_min: 100000,
  requires_sponsorship: false,
  excluded_companies: ["Example Staffing"],
  background: "Built production APIs.",
  resume_attachment_id: "resume-1",
  result_count: 10,
  frequency: "weekdays",
  next_run_at: "2026-09-18T15:00:00.000Z",
};

it("loads the My Job dashboard", async () => {
  jest.mocked(request).mockResolvedValue({ profile: null, matches: [] });
  await jobSearchApi.getJobSearch("token");
  expect(request).toHaveBeenCalledWith("/job-search", "token", {
    headers: bookmarkHeaders,
  });
});

it("saves the structured search profile", async () => {
  jest.mocked(request).mockResolvedValue({ profile: {}, matches: [] });
  await jobSearchApi.saveJobSearch("token", input);
  expect(request).toHaveBeenCalledWith("/job-search", "token", {
    method: "PUT",
    headers: bookmarkHeaders,
    body: JSON.stringify(input),
  });
});

it("updates search and match states", async () => {
  jest.mocked(request).mockResolvedValue({ profile: {}, matches: [] });

  await jobSearchApi.setJobSearchStatus("token", "paused");
  expect(request).toHaveBeenCalledWith("/job-search/status", "token", {
    method: "PATCH",
    headers: bookmarkHeaders,
    body: JSON.stringify({ status: "paused" }),
  });

  await jobSearchApi.setJobMatchSaved("token", "match-1", true);
  expect(request).toHaveBeenCalledWith("/job-search/matches/match-1", "token", {
    method: "PATCH",
    headers: bookmarkHeaders,
    body: JSON.stringify({ is_saved: true }),
  });
});

it("starts a manual search through the dedicated endpoint", async () => {
  jest.mocked(request).mockResolvedValue({ queued: true });
  await jobSearchApi.runJobSearch("token");
  expect(request).toHaveBeenCalledWith("/job-search/run", "token", {
    method: "POST",
    headers: bookmarkHeaders,
  });
});

it("deletes the search through the dedicated endpoint", async () => {
  jest.mocked(request).mockResolvedValue({ profile: {}, matches: [] });

  await jobSearchApi.deleteJobSearch("token");
  expect(request).toHaveBeenCalledWith("/job-search", "token", {
    method: "DELETE",
    headers: bookmarkHeaders,
  });
});
