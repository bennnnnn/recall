import { api } from "@/lib/api";
import {
  fetchProjectDetail,
  getCachedProjectDetail,
  invalidateProjectDetail,
  isProjectDetailFresh,
  prefetchProjectDetail,
  setProjectDetailCache,
} from "@/lib/projectDetailCache";

jest.mock("@/lib/api", () => ({
  api: {
    getProject: jest.fn(),
  },
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
  });

  it("prefetch skips when cache is already fresh", () => {
    setProjectDetailCache("proj-1", detail);
    prefetchProjectDetail("token", "proj-1");
    expect(getProject).not.toHaveBeenCalled();
  });
});
