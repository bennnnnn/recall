import { api } from "@/lib/api";
import {
  updateProjectDetailCache,
  fetchProjectDetail,
  getCachedProjectDetail,
  invalidateProjectDetail,
  isProjectDetailFresh,
  prefetchProjectDetail,
  setProjectDetailCache,
} from "@/lib/cache/projectDetailCache";

jest.mock("@/lib/api", () => ({
  api: {
    getProject: jest.fn(),
  },
}));

let mockSession = 1;
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockSession,
  requireTokenSession: jest.fn(),
}));

const getProject = api.getProject as jest.Mock;

const detail = {
  id: "proj-1",
  title: "English · Beginner",
  description: "",
  kind: "language" as const,
  target_language: "en",
  native_language: null,
  level: "level1" as const,
  daily_goal: 5,
  archived: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  mastered_count: 0,
  total_count: 0,
  stats: {
    total: 0,
    new_count: 0,
    learning_count: 0,
    mastered_count: 0,
    added_this_week: 0,
    due_for_review: 0,
    mastered_today: 0,
    pending_today: 0,
  },
  daily_history: [],
  daily_items_by_date: {},
  lists: [],
};

describe("projectDetailCache", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession += 1;
    invalidateProjectDetail("proj-1");
  });

  it("returns cached detail without refetching when fresh", async () => {
    setProjectDetailCache("proj-1", detail);
    expect(isProjectDetailFresh("proj-1")).toBe(true);
    expect(getCachedProjectDetail("proj-1")).toEqual(detail);

    const result = await fetchProjectDetail("token", "proj-1");
    expect(result).toEqual(detail);
    expect(getProject).not.toHaveBeenCalled();
  });

  it("dedupes concurrent fetches for the same project", async () => {
    let resolveFetch!: (value: typeof detail) => void;
    getProject.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const first = fetchProjectDetail("token", "proj-1", { force: true });
    const second = fetchProjectDetail("token", "proj-1", { force: true });
    resolveFetch(detail);

    const [a, b] = await Promise.all([first, second]);
    expect(a).toEqual(detail);
    expect(b).toEqual(detail);
    expect(getProject).toHaveBeenCalledTimes(1);
    expect(getProject).toHaveBeenCalledWith("token", "proj-1", { includeLists: true });
  });

  it("prefetch skips when cache is already fresh", () => {
    setProjectDetailCache("proj-1", detail);
    prefetchProjectDetail("token", "proj-1");
    expect(getProject).not.toHaveBeenCalled();
  });
});

beforeEach(() => {
  jest.clearAllMocks();
  mockSession += 1;
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
it("rejects an old account result even before a new account fetch", async () => {
  const request = deferred<typeof detail>();
  getProject.mockReturnValue(request.promise);
  const task = fetchProjectDetail("token", "account-race", { force: true });
  mockSession += 1;
  request.resolve(detail);
  expect(await task).toBeNull();
  expect(getCachedProjectDetail("account-race")).toBeUndefined();
});
it("invalidating a pending response keeps it from repopulating the entry", async () => {
  const request = deferred<typeof detail>();
  getProject.mockReturnValue(request.promise);
  const task = fetchProjectDetail("token", "invalidated", { force: true });
  invalidateProjectDetail("invalidated");
  request.resolve(detail);
  expect(await task).toBeNull();
  expect(isProjectDetailFresh("invalidated")).toBe(false);
});
it("replays confirmed item edits over a pending GET and recovers after that GET", async () => {
  const request = deferred<typeof detail>();
  getProject
    .mockReturnValueOnce(request.promise)
    .mockResolvedValueOnce({ ...detail, total_count: 8 });
  setProjectDetailCache("replay", detail);
  const task = fetchProjectDetail("token", "replay", { force: true });
  updateProjectDetailCache("replay", (row) => ({ ...row, total_count: 7 }));
  const recovery = fetchProjectDetail("token", "replay", { afterPending: true });
  request.resolve(detail);
  expect(await task).toMatchObject({ total_count: 7 });
  expect(await recovery).toMatchObject({ total_count: 8 });
  expect(getProject).toHaveBeenCalledTimes(2);
});
it("an account change while waiting for recovery cannot issue a new request", async () => {
  const request = deferred<typeof detail>();
  getProject.mockReturnValue(request.promise);
  const task = fetchProjectDetail("token", "recover-old", { force: true });
  const recovery = fetchProjectDetail("token", "recover-old", { afterPending: true });
  mockSession += 1;
  request.resolve(detail);
  await task;
  expect(await recovery).toBeNull();
  expect(getProject).toHaveBeenCalledTimes(1);
});
