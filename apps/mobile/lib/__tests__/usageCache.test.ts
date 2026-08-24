import { api } from "@/lib/api";
import {
  fetchTodayUsage,
  getCachedUsage,
  invalidateUsageCache,
} from "@/lib/cache/usageCache";

jest.mock("@/lib/api", () => ({
  api: {
    todayUsage: jest.fn(),
  },
}));

const todayUsage = api.todayUsage as jest.Mock;

const sample = {
  date: "2026-08-24",
  input_tokens: 10,
  output_tokens: 20,
  daily_limit: 100_000,
  remaining: 99_970,
};

describe("usageCache", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    invalidateUsageCache();
  });

  it("returns cached usage without refetching when fresh", async () => {
    todayUsage.mockResolvedValue(sample);
    await expect(fetchTodayUsage("tok")).resolves.toEqual(sample);
    await expect(fetchTodayUsage("tok")).resolves.toEqual(sample);
    expect(todayUsage).toHaveBeenCalledTimes(1);
    expect(getCachedUsage("tok")).toEqual(sample);
  });

  it("refetches when forced", async () => {
    todayUsage.mockResolvedValueOnce(sample).mockResolvedValueOnce({
      ...sample,
      remaining: 1,
    });
    await fetchTodayUsage("tok");
    await expect(fetchTodayUsage("tok", { force: true })).resolves.toEqual({
      ...sample,
      remaining: 1,
    });
    expect(todayUsage).toHaveBeenCalledTimes(2);
  });
});
