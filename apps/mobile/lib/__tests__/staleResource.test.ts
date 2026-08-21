import { StaleResourceCache } from "@/lib/cache/staleResource";

describe("StaleResourceCache", () => {
  it("returns fresh values without invoking the loader", async () => {
    const cache = new StaleResourceCache<string, number>(1_000);
    cache.set("key", 7);
    const loader = jest.fn(async () => 9);

    await expect(cache.fetch("key", loader)).resolves.toBe(7);
    expect(loader).not.toHaveBeenCalled();
  });

  it("deduplicates forced in-flight reads by key", async () => {
    const cache = new StaleResourceCache<string, number>(1_000);
    let resolve!: (value: number) => void;
    const loader = jest.fn(() => new Promise<number>((done) => (resolve = done)));

    const first = cache.fetch("key", loader, { force: true });
    const second = cache.fetch("key", loader, { force: true });
    resolve(11);

    await expect(Promise.all([first, second])).resolves.toEqual([11, 11]);
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it("keeps keys independent", async () => {
    const cache = new StaleResourceCache<string, number>(1_000);
    await Promise.all([
      cache.fetch("a", async () => 1),
      cache.fetch("b", async () => 2),
    ]);

    expect(cache.get("a")).toBe(1);
    expect(cache.get("b")).toBe(2);
  });

  it("preserves the timestamp for local updates", () => {
    const cache = new StaleResourceCache<string, number>(1_000);
    cache.set("key", 1, 123);
    cache.update("key", (value) => (value ?? 0) + 1);

    expect(cache.getEntry("key")).toEqual({ data: 2, fetchedAt: 123 });
  });

  it("invalidates cached and in-flight state", async () => {
    const cache = new StaleResourceCache<string, number>(1_000);
    cache.set("key", 1);
    cache.invalidate("key");

    expect(cache.get("key")).toBeUndefined();
    expect(cache.isFresh("key")).toBe(false);
  });
});
