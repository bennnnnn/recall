/**
 * A purchase the store holds blocks a second one. On Android the other period bought while one
 * waits starts its own subscription, and a Play slow payment can wait for days: the hold there
 * is kept on disk for its account, through relaunches, for a week. iOS keeps it for 30 minutes.
 */
const mockPlatform = { OS: "android" };
jest.mock("react-native", () => ({ Platform: mockPlatform }));

/** The documents directory by file name; the cache directory's files as `cache/<name>`. */
const mockDisk = new Map<string, string>();
const mockKey = (path: string) => path.replace("file:///docs/", "").replace("file:///cache/", "cache/");
jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "file:///docs/",
  cacheDirectory: "file:///cache/",
  getInfoAsync: async (path: string) => ({ exists: mockDisk.has(mockKey(path)) }),
  readAsStringAsync: async (path: string) => mockDisk.get(mockKey(path)) ?? "",
  writeAsStringAsync: async (path: string, contents: string) => {
    mockDisk.set(mockKey(path), contents);
  },
  moveAsync: async ({ from, to }: { from: string; to: string }) => {
    mockDisk.set(mockKey(to), mockDisk.get(mockKey(from)) ?? "");
    mockDisk.delete(mockKey(from));
  },
  deleteAsync: async (path: string) => {
    mockDisk.delete(mockKey(path));
  },
}));

type HeldModule = typeof import("@/features/billing/model/heldPurchase");

const T0 = Date.UTC(2026, 10, 8, 12);
const MINUTE = 60_000;
const DAY = 24 * 60 * MINUTE;

/** The module as a fresh launch loads it: nothing in memory, the disk as it was. */
function launch(): HeldModule {
  let loaded!: HeldModule;
  jest.isolateModules(() => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- a fresh copy per launch
    loaded = require("@/features/billing/model/heldPurchase") as HeldModule;
  });
  return loaded;
}

const settle = () => new Promise<void>((resolve) => setImmediate(resolve));

beforeEach(() => {
  mockDisk.clear();
  mockPlatform.OS = "android";
});

describe("on Android", () => {
  it("keeps a held purchase through a relaunch, for its own account", async () => {
    launch().holdPurchase("user-1", "pro", T0);
    await settle();

    const relaunched = launch();
    await relaunched.loadHeldPurchase("user-1", T0 + 3 * DAY);
    expect(relaunched.heldPurchase()).toBe("pro");
  });

  it("keeps the hold an earlier version wrote in the cache directory, now in the documents directory", async () => {
    mockDisk.set("cache/recall-held-purchase.txt", `user-1|pro|${T0}`);
    const upgraded = launch();
    await upgraded.loadHeldPurchase("user-1", T0 + DAY);
    expect(upgraded.heldPurchase()).toBe("pro");
    expect([...mockDisk]).toEqual([["recall-held-purchase.txt", `user-1|pro|${T0}`]]);
  });

  it("lets go of a hold an older version kept for Plus, which is no plan any more", async () => {
    mockDisk.set("recall-held-purchase.txt", `user-1|plus|${T0}`);
    const relaunched = launch();
    await relaunched.loadHeldPurchase("user-1", T0 + DAY);
    expect(relaunched.heldPurchase()).toBeNull();
    expect(mockDisk.size).toBe(0);
  });

  it("does not let go after 30 minutes, only after a week", async () => {
    const held = launch();
    held.holdPurchase("user-1", "pro", T0);
    held.expireHeldPurchase(T0 + 31 * MINUTE);
    expect(held.heldPurchase()).toBe("pro");
    held.expireHeldPurchase(T0 + 7 * DAY);
    expect(held.heldPurchase()).toBeNull();
    await settle();
    expect(mockDisk.size).toBe(0);
  });

  it.each([
    ["another account's hold", "user-2", T0 + MINUTE],
    ["a hold past its week", "user-1", T0 + 8 * DAY],
  ])("deletes %s instead of loading it", async (_case, account, now) => {
    launch().holdPurchase("user-1", "pro", T0);
    await settle();
    const relaunched = launch();
    await relaunched.loadHeldPurchase(account, now);
    expect(relaunched.heldPurchase()).toBeNull();
    expect(mockDisk.size).toBe(0);
  });

  it("lets go once the store grants the plan, and not while it says free", async () => {
    const held = launch();
    held.holdPurchase("user-1", "pro", T0);
    held.settleHeldPurchase("free");
    expect(held.heldPurchase()).toBe("pro");
    held.settleHeldPurchase("pro");
    expect(held.heldPurchase()).toBeNull();
    await settle();
    expect(mockDisk.size).toBe(0);
  });

  it("forgets the hold, here and on disk, when released (a restore or a sign-out)", async () => {
    const held = launch();
    held.holdPurchase("user-1", "pro", T0);
    await held.releaseHeldPurchase();
    expect(held.heldPurchase()).toBeNull();
    expect(mockDisk.size).toBe(0);
  });
});

describe("on iOS", () => {
  beforeEach(() => {
    mockPlatform.OS = "ios";
  });

  it("keeps the hold for the session only, and lets go after 30 minutes", async () => {
    const held = launch();
    held.holdPurchase("user-1", "pro", T0);
    await settle();
    expect(mockDisk.size).toBe(0);
    held.expireHeldPurchase(T0 + 29 * MINUTE);
    expect(held.heldPurchase()).toBe("pro");
    held.expireHeldPurchase(T0 + 30 * MINUTE);
    expect(held.heldPurchase()).toBeNull();
  });
});
