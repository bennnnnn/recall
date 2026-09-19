import { act, renderHook, waitFor } from "@testing-library/react-native";

import { useJobSearch } from "@/hooks/useJobSearch";
import {
  api,
  type JobMatch,
  type JobSearchDashboard,
  type JobSearchInput,
  type JobSearchProfile,
} from "@/lib/api";

const mockFeedbackError = jest.fn();
let mockCurrent = true;

jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token-a", user: { id: "account-a" } }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => ({ error: mockFeedbackError }),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/lib/jobSearch/matchCache", () => ({
  cacheJobMatches: jest.fn(),
}));
jest.mock("@/lib/api", () => ({
  api: {
    getJobSearch: jest.fn(),
    saveJobSearch: jest.fn(),
    setJobSearchStatus: jest.fn(),
    setJobMatchStatus: jest.fn(),
    deleteJobSearch: jest.fn(),
  },
}));

const mockApi = jest.mocked(api);

function profile(overrides: Partial<JobSearchProfile> = {}): JobSearchProfile {
  return {
    id: "profile-a",
    target_roles: ["Registered Nurse"],
    skills: ["Triage"],
    location: "Berlin",
    work_modes: ["onsite"],
    experience_levels: ["mid"],
    salary_min: 60000,
    requires_sponsorship: false,
    excluded_companies: [],
    background: null,
    resume_attachment_id: null,
    resume_filename: null,
    result_count: 5,
    frequency: "weekly",
    next_run_at: "2026-09-20T08:00:00.000Z",
    status: "active",
    last_run_at: null,
    last_run_status: null,
    created_at: "2026-09-18T00:00:00.000Z",
    updated_at: "2026-09-18T00:00:00.000Z",
    ...overrides,
  };
}

function match(overrides: Partial<JobMatch> = {}): JobMatch {
  return {
    id: "match-a",
    title: "Registered Nurse",
    company: "Acme Health",
    location: "Berlin",
    work_mode: "onsite",
    salary: null,
    experience: null,
    match_score: 88,
    url: "https://jobs.example.com/1",
    source: "jobs.example.com",
    posted_at: null,
    summary: null,
    match_reasons: [],
    gap: null,
    found_at: "2026-09-18T00:00:00.000Z",
    status: "new",
    notes: null,
    ...overrides,
  };
}

const input: JobSearchInput = {
  target_roles: ["Staff Nurse"],
  skills: ["Triage", "ICU"],
  location: "Hamburg",
  work_modes: ["hybrid"],
  experience_levels: ["senior"],
  salary_min: 70000,
  requires_sponsorship: null,
  excluded_companies: ["Example Corp"],
  background: null,
  resume_attachment_id: "resume-a",
  result_count: 10,
  frequency: "weekdays",
  next_run_at: "2026-09-21T08:00:00.000Z",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

async function renderSearch(initial: JobSearchDashboard) {
  mockApi.getJobSearch.mockResolvedValue(initial);
  const hook = await renderHook(() => useJobSearch(() => mockCurrent));
  await waitFor(() => expect(hook.result.current.loading).toBe(false));
  return hook;
}

beforeEach(() => {
  jest.clearAllMocks();
  mockCurrent = true;
});

test("pauses immediately and reconciles the server dashboard", async () => {
  const initial = { profile: profile(), matches: [match()] };
  const saved = {
    profile: profile({ status: "paused", updated_at: "2026-09-19T00:00:00.000Z" }),
    matches: [match({ status: "saved" })],
  };
  const request = deferred<JobSearchDashboard>();
  mockApi.setJobSearchStatus.mockReturnValue(request.promise);
  const { result } = await renderSearch(initial);

  let pending!: Promise<void>;
  await act(() => {
    pending = result.current.setSearchStatus("paused");
  });
  expect(result.current.dashboard.profile?.status).toBe("paused");
  expect(result.current.busy).toBe(true);

  await act(async () => {
    request.resolve(saved);
    await pending;
  });
  expect(result.current.dashboard).toEqual(saved);
  expect(result.current.busy).toBe(false);
});

test("rolls a failed pause back to its dashboard snapshot", async () => {
  const initial = { profile: profile(), matches: [match()] };
  const request = deferred<JobSearchDashboard>();
  mockApi.setJobSearchStatus.mockReturnValue(request.promise);
  const { result } = await renderSearch(initial);

  let pending!: Promise<void>;
  await act(() => {
    pending = result.current.setSearchStatus("paused");
  });
  expect(result.current.dashboard.profile?.status).toBe("paused");

  await act(async () => {
    request.reject(new Error("offline"));
    await pending;
  });
  expect(result.current.dashboard).toEqual(initial);
  expect(mockFeedbackError).toHaveBeenCalledWith("my_job.error_update");
});

test("optimistically creates a complete profile and reconciles save success", async () => {
  const request = deferred<JobSearchDashboard>();
  const saved = { profile: profile({ id: "server-profile", ...input }), matches: [] };
  mockApi.saveJobSearch.mockReturnValue(request.promise);
  const { result } = await renderSearch({ profile: null, matches: [] });

  let pending!: Promise<boolean>;
  await act(() => {
    pending = result.current.save(input);
  });
  expect(result.current.dashboard.profile).toMatchObject({
    id: "local-job-search",
    ...input,
    resume_filename: null,
    status: "active",
    last_run_at: null,
    last_run_status: null,
  });
  expect(result.current.dashboard.profile?.created_at).toEqual(expect.any(String));
  expect(result.current.dashboard.profile?.updated_at).toEqual(expect.any(String));

  await act(async () => {
    request.resolve(saved);
    await expect(pending).resolves.toBe(true);
  });
  expect(result.current.dashboard).toEqual(saved);
});

test("rolls a failed save back and reports false so setup remains open", async () => {
  const initial = { profile: profile(), matches: [match()] };
  const request = deferred<JobSearchDashboard>();
  mockApi.saveJobSearch.mockReturnValue(request.promise);
  const { result } = await renderSearch(initial);

  let pending!: Promise<boolean>;
  await act(() => {
    pending = result.current.save(input);
  });
  expect(result.current.dashboard.profile?.target_roles).toEqual(["Staff Nurse"]);

  let saved = true;
  await act(async () => {
    request.reject(new Error("offline"));
    saved = await pending;
  });
  expect(saved).toBe(false);
  expect(result.current.dashboard).toEqual(initial);
  expect(mockFeedbackError).toHaveBeenCalledWith("offline");
});

test("deduplicates busy profile mutations", async () => {
  const request = deferred<JobSearchDashboard>();
  mockApi.saveJobSearch.mockReturnValue(request.promise);
  const initial = { profile: profile(), matches: [] };
  const { result } = await renderSearch(initial);

  let pending!: Promise<boolean>;
  await act(() => {
    pending = result.current.save(input);
  });
  await act(async () => {
    await expect(result.current.save(input)).resolves.toBe(false);
    await result.current.setSearchStatus("paused");
  });
  expect(mockApi.saveJobSearch).toHaveBeenCalledTimes(1);
  expect(mockApi.setJobSearchStatus).not.toHaveBeenCalled();

  await act(async () => {
    request.resolve(initial);
    await pending;
  });
});

test("blocks stale views and ignores responses after ownership changes", async () => {
  const initial = { profile: profile(), matches: [] };
  const blocked = await renderSearch(initial);
  mockCurrent = false;
  await act(async () => {
    await blocked.result.current.setSearchStatus("paused");
    await expect(blocked.result.current.save(input)).resolves.toBe(false);
  });
  expect(mockApi.setJobSearchStatus).not.toHaveBeenCalled();
  expect(mockApi.saveJobSearch).not.toHaveBeenCalled();

  mockCurrent = true;
  const request = deferred<JobSearchDashboard>();
  mockApi.setJobSearchStatus.mockReturnValue(request.promise);
  let pending!: Promise<void>;
  await act(() => {
    pending = blocked.result.current.setSearchStatus("paused");
  });
  mockCurrent = false;
  await act(async () => {
    request.resolve({ profile: profile({ status: "active" }), matches: [match()] });
    await pending;
  });
  expect(blocked.result.current.dashboard.profile?.status).toBe("paused");
});

test("keeps match status optimistic with success reconciliation and rollback", async () => {
  const initial = { profile: profile(), matches: [match()] };
  const first = deferred<JobSearchDashboard>();
  mockApi.setJobMatchStatus.mockReturnValueOnce(first.promise);
  const { result } = await renderSearch(initial);

  let success!: Promise<void>;
  await act(() => {
    success = result.current.setMatchStatus("match-a", "saved");
  });
  expect(result.current.dashboard.matches[0].status).toBe("saved");
  const reconciled = {
    profile: profile(),
    matches: [match({ status: "applied", notes: "Server copy" })],
  };
  await act(async () => {
    first.resolve(reconciled);
    await success;
  });
  expect(result.current.dashboard).toEqual(reconciled);

  const second = deferred<JobSearchDashboard>();
  mockApi.setJobMatchStatus.mockReturnValueOnce(second.promise);
  let failure!: Promise<void>;
  await act(() => {
    failure = result.current.setMatchStatus("match-a", "hidden");
  });
  expect(result.current.dashboard.matches[0].status).toBe("hidden");
  await act(async () => {
    second.reject(new Error("offline"));
    await failure;
  });
  expect(result.current.dashboard).toEqual(reconciled);
  expect(mockFeedbackError).toHaveBeenCalledWith("my_job.error_match");
});
