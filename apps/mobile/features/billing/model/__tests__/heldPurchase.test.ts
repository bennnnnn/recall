/**
 * A purchase the store holds blocks a second one. On Android a Pro bought while Plus waits
 * starts its own subscription, and a Play slow payment can wait for days: the hold there is
 * kept on disk for its account, through relaunches, for a week. iOS keeps it for 30 minutes.
 */
const mockPlatform = { OS: "android" };
jest.mock("react-native", () => ({ Platform: mockPlatform }));

const mockDisk = new Map<string, string>();
jest.mock("@/lib/cache/cacheFile", () => ({
  cacheFile: (name: string) => ({
    read: async () => mockDisk.get(name) ?? null,
    readSync: () => mockDisk.get(name) ?? null,
    write: async (contents: string) => {
      mockDisk.set(name, contents);
    },
    clear: async () => {
      mockDisk.delete(name);
    },
  }),
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
  it("keeps a held Plus through a relaunch, for its own account", async () => {
    launch().holdPurchase("user-1", "plus", T0);
    await settle();

    const relaunched = launch();
    await relaunched.loadHeldPurchase("user-1", T0 + 3 * DAY);
    expect(relaunched.heldPurchase()).toBe("plus");
  });

  it("does not let go after 30 minutes, only after a week", async () => {
    const held = launch();
    held.holdPurchase("user-1", "plus", T0);
    held.expireHeldPurchase(T0 + 31 * MINUTE);
    expect(held.heldPurchase()).toBe("plus");
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

  it("lets go once the store grants the plan or a higher one, and not for a lower one", async () => {
    const held = launch();
    held.holdPurchase("user-1", "pro", T0);
    held.settleHeldPurchase("plus");
    expect(held.heldPurchase()).toBe("pro");
    held.settleHeldPurchase("pro");
    expect(held.heldPurchase()).toBeNull();
    await settle();
    expect(mockDisk.size).toBe(0);
  });

  it("forgets the hold, here and on disk, when released (a restore or a sign-out)", async () => {
    const held = launch();
    held.holdPurchase("user-1", "plus", T0);
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
    held.holdPurchase("user-1", "plus", T0);
    await settle();
    expect(mockDisk.size).toBe(0);
    held.expireHeldPurchase(T0 + 29 * MINUTE);
    expect(held.heldPurchase()).toBe("plus");
    held.expireHeldPurchase(T0 + 30 * MINUTE);
    expect(held.heldPurchase()).toBeNull();
  });
});
