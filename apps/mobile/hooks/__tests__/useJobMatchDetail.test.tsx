import { act, renderHook, waitFor } from "@testing-library/react-native";
import { Alert } from "react-native";

import { useJobMatchDetail } from "@/hooks/useJobMatchDetail";
import type { JobMatch, JobSearchDashboard } from "@/lib/api";
import {
  cacheJobMatches,
  clearJobMatchCache,
  getCachedJobMatch,
} from "@/lib/jobSearch/matchCache";

const mockGetJobSearch = jest.fn();
const mockSetJobMatchStatus = jest.fn();
const mockGenerateCoverLetter = jest.fn();
const mockBack = jest.fn();
let mockCurrent = true;
let mockAccountId = "account-a";

jest.mock("expo-router", () => ({
  useRouter: () => ({ back: mockBack }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token-a", user: { id: mockAccountId } }),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));
jest.mock("@/lib/api", () => ({
  api: {
    getJobSearch: (...args: unknown[]) => mockGetJobSearch(...args),
    setJobMatchStatus: (...args: unknown[]) => mockSetJobMatchStatus(...args),
    generateCoverLetter: (...args: unknown[]) => mockGenerateCoverLetter(...args),
  },
}));

function match(overrides: Partial<JobMatch> = {}): JobMatch {
  return {
    id: "m1",
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
    found_at: "2026-09-18T00:00:00Z",
    status: "new",
    notes: null,
    ...overrides,
  };
}

function dashboard(matches: JobMatch[]): JobSearchDashboard {
  return { profile: null, matches };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  clearJobMatchCache();
  jest.clearAllMocks();
  mockGetJobSearch.mockReset();
  mockSetJobMatchStatus.mockReset();
  mockGenerateCoverLetter.mockReset();
  mockCurrent = true;
  mockAccountId = "account-a";
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});

afterEach(() => jest.restoreAllMocks());

test("hydrates from cache without a cold dashboard request", async () => {
  cacheJobMatches("account-a", [match({ notes: "Cached note" })]);
  const { result } = await renderHook(() =>
    useJobMatchDetail("m1", () => mockCurrent),
  );
  expect(result.current.match?.title).toBe("Registered Nurse");
  expect(result.current.notesDraft).toBe("Cached note");
  expect(result.current.loading).toBe(false);
  expect(mockGetJobSearch).not.toHaveBeenCalled();
});

test("does not hydrate a match cached by an earlier account session", async () => {
  cacheJobMatches("account-a", [match()]);
  mockAccountId = "account-b";
  mockGetJobSearch.mockResolvedValue(dashboard([]));
  const { result } = await renderHook(() =>
    useJobMatchDetail("m1", () => mockCurrent),
  );
  expect(result.current.match).toBeNull();
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(mockGetJobSearch).toHaveBeenCalledWith("token-a");
});

test("keeps first-load failure separate from true not-found and retries", async () => {
  mockGetJobSearch
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(dashboard([]));
  const { result } = await renderHook(() =>
    useJobMatchDetail("m1", () => mockCurrent),
  );
  await waitFor(() => expect(result.current.loadError).toBe(true));
  expect(result.current.match).toBeNull();

  await act(async () => {
    await result.current.load();
  });
  expect(result.current.loading).toBe(false);
  expect(result.current.loadError).toBe(false);
  expect(result.current.match).toBeNull();
});

test("ignores a cold response after the view owner becomes stale", async () => {
  const pending = deferred<JobSearchDashboard>();
  mockGetJobSearch.mockReturnValue(pending.promise);
  const { result } = await renderHook(() =>
    useJobMatchDetail("m1", () => mockCurrent),
  );
  mockCurrent = false;
  await act(async () => {
    pending.resolve(dashboard([match()]));
  });
  expect(result.current.match).toBeNull();
  expect(getCachedJobMatch("account-a", "m1")).toBeNull();
});

test("rolls back optimistic status and notes when the write fails", async () => {
  cacheJobMatches("account-a", [match({ notes: "Old note" })]);
  const statusWrite = deferred<JobSearchDashboard>();
  mockSetJobMatchStatus.mockReturnValueOnce(statusWrite.promise);
  const { result } = await renderHook(() =>
    useJobMatchDetail("m1", () => mockCurrent),
  );

  let statusPromise!: Promise<boolean>;
  await act(() => {
    statusPromise = result.current.updateStatus("saved");
  });
  expect(result.current.match?.status).toBe("saved");
  await act(async () => {
    statusWrite.reject(new Error("write failed"));
    await statusPromise;
  });
  expect(result.current.match?.status).toBe("new");
  expect(getCachedJobMatch("account-a", "m1")?.status).toBe("new");

  const notesWrite = deferred<JobSearchDashboard>();
  mockSetJobMatchStatus.mockReturnValueOnce(notesWrite.promise);
  await act(() => {
    result.current.setNotesDraft("New note");
  });
  await act(() => {
    result.current.saveNotes();
  });
  expect(result.current.match?.notes).toBe("New note");
  await act(async () => {
    notesWrite.reject(new Error("write failed"));
  });
  await waitFor(() => expect(result.current.notesDraft).toBe("Old note"));
  expect(result.current.match?.notes).toBe("Old note");
});

test("owns cover-letter loading and result state", async () => {
  cacheJobMatches("account-a", [match()]);
  const pending = deferred<{ cover_letter: string }>();
  mockGenerateCoverLetter.mockReturnValue(pending.promise);
  const { result } = await renderHook(() =>
    useJobMatchDetail("m1", () => mockCurrent),
  );

  await act(() => {
    void result.current.generateLetter();
  });
  expect(result.current.letterOpen).toBe(true);
  expect(result.current.letterLoading).toBe(true);
  await act(async () => {
    pending.resolve({ cover_letter: "Dear team" });
  });
  expect(result.current.letter).toBe("Dear team");
  expect(result.current.letterLoading).toBe(false);
});
