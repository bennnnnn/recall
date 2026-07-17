import { api } from "@/lib/api";
import {
  fetchMemories,
  getCachedMemories,
  invalidateMemoriesCache,
  isMemoriesFresh,
  prefetchMemories,
  setMemoriesCache,
} from "@/lib/memoryListCache";

jest.mock("@/lib/api", () => ({
  api: {
    listMemories: jest.fn(),
  },
}));

const listMemories = api.listMemories as jest.Mock;

const sample = [
  {
    id: "m1",
    type: "profile",
    text: "Name is Bini.",
    confidence: 0.9,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

describe("memoryListCache", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    invalidateMemoriesCache();
  });

  it("returns cached memories without refetching when fresh", async () => {
    setMemoriesCache(sample);
    expect(isMemoriesFresh()).toBe(true);
    expect(getCachedMemories()).toEqual(sample);

    const result = await fetchMemories("token");
    expect(result).toEqual(sample);
    expect(listMemories).not.toHaveBeenCalled();
  });

  it("dedupes concurrent fetches", async () => {
    let resolveFetch!: (value: typeof sample) => void;
    listMemories.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const first = fetchMemories("token", { force: true });
    const second = fetchMemories("token", { force: true });
    resolveFetch(sample);

    const [a, b] = await Promise.all([first, second]);
    expect(a).toEqual(sample);
    expect(b).toEqual(sample);
    expect(listMemories).toHaveBeenCalledTimes(1);
  });

  it("prefetch skips when cache is already fresh", () => {
    setMemoriesCache(sample);
    prefetchMemories("token");
    expect(listMemories).not.toHaveBeenCalled();
  });
});
