import { act, renderHook, waitFor } from "@testing-library/react-native";
import { AppState } from "react-native";

import { useJobSearch } from "@/features/job-search/hooks/useJobSearch";
import {
  api,
  type JobMatch,
  type JobSearchDashboard,
  type JobSearchInput,
  type JobSearchProfile,
} from "@/lib/api";

jest.mock("expo-router", () => ({ useFocusEffect: (callback: () => void) => { const React = jest.requireActual("react"); React.useEffect(callback, [callback]); } }));
const mockRandomUUID = jest.fn();
jest.mock("expo-crypto", () => ({ randomUUID: () => mockRandomUUID() }));

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
jest.mock("@/features/job-search/model/matchCache", () => ({
  cacheJobMatches: jest.fn(),
}));
jest.mock("@/lib/api", () => ({
  api: {
    getJobSearch: jest.fn(),
    getJobMatches: jest.fn(),
    saveJobSearch: jest.fn(),
    setJobSearchStatus: jest.fn(),
    setJobMatchStatus: jest.fn(),
    setJobMatchSaved: jest.fn(),
    runJobSearch: jest.fn(),
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
    is_saved: false,
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
  let request = 0;
  mockRandomUUID.mockImplementation(() => `search-request-${++request}`);
  mockCurrent = true;
});

test("pauses immediately and reconciles the server dashboard", async () => {
  const initial = { profile: profile(), matches: [match()] };
  const saved = {
    profile: profile({ status: "paused", updated_at: "2026-09-19T00:00:00.000Z" }),
    matches: [match({ is_saved: true })],
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

test("keeps match stage optimistic with success reconciliation and rollback", async () => {
  const initial = { profile: profile(), matches: [match()] };
  const first = deferred<JobSearchDashboard>();
  mockApi.setJobMatchStatus.mockReturnValueOnce(first.promise);
  const { result } = await renderSearch(initial);

  let success!: Promise<void>;
  await act(() => {
    success = result.current.setMatchStatus("match-a", "applied");
  });
  expect(result.current.dashboard.matches[0].status).toBe("applied");
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

test("bookmarks an applied match without changing its stage", async () => {
  const initial = {
    profile: profile(),
    matches: [match({ status: "applied", is_saved: false })],
  };
  const request = deferred<JobSearchDashboard>();
  mockApi.setJobMatchSaved.mockReturnValueOnce(request.promise);
  const { result } = await renderSearch(initial);

  let pending!: Promise<void>;
  await act(() => {
    pending = result.current.setMatchSaved("match-a", true);
  });
  expect(result.current.dashboard.matches[0]).toMatchObject({
    status: "applied",
    is_saved: true,
  });

  await act(async () => {
    request.resolve({
      profile: profile(),
      matches: [match({ status: "applied", is_saved: true })],
    });
    await pending;
  });
  expect(result.current.dashboard.matches[0]).toMatchObject({
    status: "applied",
    is_saved: true,
  });
});

test("retries a failed run optimistically and restores the error on failure", async () => {
  const initial = {
    profile: profile({ last_run_status: "error" }),
    matches: [match()],
  };
  const request = deferred<{ queued: boolean }>();
  mockApi.runJobSearch.mockReturnValue(request.promise);
  const { result } = await renderSearch(initial);

  let pending!: Promise<boolean>;
  await act(() => {
    pending = result.current.runNow();
  });
  expect(result.current.dashboard.profile?.last_run_status).toBeNull();
  expect(result.current.busy).toBe(true);

  await act(async () => {
    request.reject(new Error("offline"));
    await expect(pending).resolves.toBe(false);
  });
  expect(result.current.dashboard).toEqual(initial);
  expect(mockFeedbackError).toHaveBeenCalledWith("offline");
});


test("pages history, keeps loaded jobs when applying, and loads Applied separately", async () => {
  mockApi.getJobSearch.mockResolvedValue({ profile: profile(), matches: [] });
  mockApi.getJobMatches.mockResolvedValueOnce({ matches: [match()], next_offset: 30 });
  const hook = await renderHook(({ view }: { view: "all" | "applied" }) => useJobSearch(() => mockCurrent, undefined, view), { initialProps: { view: "all" as "all" | "applied" } });
  await waitFor(() => expect(hook.result.current.loading).toBe(false));
  expect(mockApi.getJobSearch).toHaveBeenCalledWith("token-a", false);
  expect(mockApi.getJobMatches).toHaveBeenLastCalledWith("token-a", 0, undefined, "all");
  mockApi.getJobMatches.mockResolvedValueOnce({ matches: [match({ id: "older" })], next_offset: null });
  await act(() => hook.result.current.loadMore());
  expect(mockApi.getJobMatches).toHaveBeenLastCalledWith("token-a", 30, undefined, "all");
  mockApi.setJobMatchStatus.mockResolvedValue({ profile: profile(), matches: [match({ status: "applied" })] });
  await act(() => hook.result.current.setMatchStatus("older", "applied"));
  expect(hook.result.current.dashboard.matches.map(item => [item.id, item.status])).toEqual([["match-a", "new"], ["older", "applied"]]);
  mockApi.getJobMatches.mockResolvedValueOnce({ matches: [match({ id: "older", status: "applied", is_saved: true })], next_offset: null });
  await hook.rerender({ view: "applied" });
  await waitFor(() => expect(hook.result.current.loading).toBe(false));
  expect(hook.result.current.dashboard.matches.map(item => item.id)).toEqual(["older"]);
});

test("ignores a late history page after switching to Applied", async () => {
  mockApi.getJobSearch.mockResolvedValue({ profile: profile(), matches: [] });
  mockApi.getJobMatches.mockResolvedValueOnce({ matches: [match()], next_offset: 30 });
  const hook = await renderHook(({ view }: { view: "all" | "applied" }) => useJobSearch(() => mockCurrent, undefined, view), { initialProps: { view: "all" as "all" | "applied" } });
  await waitFor(() => expect(hook.result.current.loading).toBe(false));
  const page = deferred<{ matches: JobMatch[]; next_offset: number | null }>();
  mockApi.getJobMatches.mockReturnValueOnce(page.promise);
  let pending!: Promise<void>;
  await act(() => { pending = hook.result.current.loadMore(); });
  mockApi.getJobMatches.mockResolvedValueOnce({ matches: [match({ id: "application", status: "applied" })], next_offset: null });
  await hook.rerender({ view: "applied" });
  await waitFor(() => expect(hook.result.current.loading).toBe(false));
  await act(async () => { page.resolve({ matches: [match({ id: "old-history" })], next_offset: null }); await pending; });
  expect(hook.result.current.dashboard.matches.map(item => item.id)).toEqual(["application"]);
});

test("unmarking Applied keeps the history page and adjusts the next page offset", async () => {
  mockApi.getJobSearch.mockResolvedValue({ profile: profile(), matches: [] });
  mockApi.getJobMatches.mockResolvedValue({ matches: [match({ status: "applied", is_saved: true })], next_offset: 30 });
  const hook = await renderHook(() => useJobSearch(() => mockCurrent, undefined, "applied"));
  await waitFor(() => expect(hook.result.current.loading).toBe(false));
  mockApi.setJobMatchStatus.mockResolvedValue({ profile: profile(), matches: [match({ status: "new", is_saved: true })] });
  await act(() => hook.result.current.setMatchStatus("match-a", "new"));
  expect(hook.result.current.dashboard.matches).toEqual([]);
  expect(hook.result.current.dashboard.next_offset).toBe(29);
});


test("refreshes the chosen tab after switching while an application update is pending", async () => {
  mockApi.getJobSearch.mockResolvedValue({ profile: profile(), matches: [] });
  mockApi.getJobMatches.mockResolvedValueOnce({ matches: [match()], next_offset: null });
  const hook = await renderHook(({ view }: { view: "all" | "applied" }) => useJobSearch(() => mockCurrent, undefined, view), { initialProps: { view: "all" as "all" | "applied" } });
  await waitFor(() => expect(hook.result.current.loading).toBe(false));
  const update = deferred<JobSearchDashboard>();
  mockApi.setJobMatchStatus.mockReturnValueOnce(update.promise);
  let pending!: Promise<void>;
  await act(() => { pending = hook.result.current.setMatchStatus("match-a", "applied"); });
  await hook.rerender({ view: "applied" });
  expect(hook.result.current.dashboard.matches).toEqual([]);
  mockApi.getJobMatches.mockResolvedValueOnce({ matches: [match({ status: "applied" })], next_offset: null });
  await act(async () => { update.resolve({ profile: profile(), matches: [match({ status: "applied" })] }); await pending; });
  await waitFor(() => expect(hook.result.current.loading).toBe(false));
  expect(mockApi.getJobMatches).toHaveBeenLastCalledWith("token-a", 0, undefined, "applied");
  expect(hook.result.current.dashboard.matches[0].status).toBe("applied");
});


test("reuses the logical search key when the dashboard refresh fails after admission", async () => {
  const initial = { profile: profile(), matches: [] };
  const { result } = await renderSearch(initial);
  mockApi.runJobSearch.mockResolvedValue({ queued: true });
  mockApi.getJobSearch.mockRejectedValueOnce(new Error("offline"));
  await act(async () => { await expect(result.current.runNow()).resolves.toBe(false); });
  await act(async () => { await expect(result.current.runNow()).resolves.toBe(true); });
  expect(mockApi.runJobSearch.mock.calls.slice(0, 2)).toEqual([
    ["token-a", "search-request-1"], ["token-a", "search-request-1"],
  ]);
  await act(async () => { await expect(result.current.runNow()).resolves.toBe(true); });
  expect(mockApi.runJobSearch).toHaveBeenLastCalledWith("token-a", "search-request-2");
});

test.each([true, false])("autoRefresh=%s controls polling and foreground refresh", async (autoRefresh) => {
  jest.useFakeTimers();
  const state = AppState.currentState;
  AppState.currentState = "active";
  const listener = jest.spyOn(AppState, "addEventListener");
  const initial: JobSearchDashboard = { profile: profile(), matches: [], latest_run: {
    id: "run", state: "running", profile_revision: 1, manual: true,
    created_at: "2026-09-18T00:00:00.000Z", qualifying_count: 0, possible_count: 0, new_match_count: 0,
  } };
  mockApi.getJobSearch.mockResolvedValue(initial);
  const hook = await renderHook(() => useJobSearch(() => mockCurrent, undefined, undefined, { autoRefresh }));
  try {
    await act(async () => {});
    expect(mockApi.getJobSearch).toHaveBeenCalledTimes(1);
    await act(async () => { jest.advanceTimersByTime(9000); });
    expect(mockApi.getJobSearch).toHaveBeenCalledTimes(autoRefresh ? 4 : 1);
    if (autoRefresh) {
      const callback = listener.mock.calls.at(-1)![1];
      await act(async () => { callback("active"); });
      expect(mockApi.getJobSearch).toHaveBeenCalledTimes(5);
    } else {
      expect(listener).not.toHaveBeenCalled();
    }
  } finally {
    await hook.unmount();
    listener.mockRestore();
    AppState.currentState = state;
    jest.useRealTimers();
  }
});
