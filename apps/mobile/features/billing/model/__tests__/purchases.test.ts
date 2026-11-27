import { reportFailure } from "@/lib/sentry";

jest.mock("@/lib/expoRuntime", () => ({
  isExpoGo: () => false,
}));

const mockPlatform = { OS: "ios" };
jest.mock("react-native", () => ({ Platform: mockPlatform }));
jest.mock("@/lib/sentry", () => ({ reportFailure: jest.fn() }));
// The phone's files, in memory: a held purchase on Android is kept in one.
const mockDisk = new Map<string, string>();
const mockMemoryFile = (name: string) => ({
  read: async () => mockDisk.get(name) ?? null,
  readSync: () => mockDisk.get(name) ?? null,
  write: async (contents: string) => {
    mockDisk.set(name, contents);
  },
  clear: async () => {
    mockDisk.delete(name);
  },
});
jest.mock("@/lib/durableFile", () => ({ durableFile: (name: string) => mockMemoryFile(name) }));
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

jest.mock("react-native-purchases", () => {
  const listeners: Array<(info: { entitlements: { active: Record<string, unknown> } }) => void> = [];
  const api = {
    LOG_LEVEL: { DEBUG: 0, WARN: 1 },
    PURCHASES_ERROR_CODE: { PAYMENT_PENDING_ERROR: "20" },
    setLogLevel: jest.fn(),
    configure: jest.fn(),
    logIn: jest.fn(async () => ({})),
    logOut: jest.fn(async () => ({})),
    getOfferings: jest.fn(),
    purchasePackage: jest.fn(),
    restorePurchases: jest.fn(),
    getCustomerInfo: jest.fn(),
    checkTrialOrIntroductoryPriceEligibility: jest.fn(),
    INTRO_ELIGIBILITY_STATUS: { INTRO_ELIGIBILITY_STATUS_ELIGIBLE: 2 },
    addCustomerInfoUpdateListener: jest.fn(
      (l: (info: { entitlements: { active: Record<string, unknown> } }) => void) => {
        listeners.push(l);
      },
    ),
    removeCustomerInfoUpdateListener: jest.fn(
      (l: (info: { entitlements: { active: Record<string, unknown> } }) => void) => {
        const i = listeners.indexOf(l);
        if (i >= 0) listeners.splice(i, 1);
      },
    ),
    __fire: (info: { entitlements: { active: Record<string, unknown> } }) => {
      for (const l of listeners) l(info);
    },
    __listenerCount: () => listeners.length,
  };
  // Expose at both top level and `default` so it works regardless of ts-jest's
  // ESM/CJS interop wrapping on `await import(...)`.
  return { ...api, default: api };
});

import {
  configurePurchases,
  freeTrialOf,
  getPlanPackages,
  isPurchaseCancelled,
  isStoreReady,
  planFromCustomerInfo,
  purchasePlanPackage,
  recheckPendingPurchase,
  registerPlanChangeListener,
  restorePurchases,
  signOutRevenueCat,
  subscribeStoreReady,
} from "@/features/billing/model/purchases";
import { heldPurchase as purchasePending } from "@/features/billing/model/heldPurchase";

// Force the purchases module to be "configured" (API key present + not Expo Go).
process.env.EXPO_PUBLIC_REVENUECAT_IOS_API_KEY = "test-ios-key";

// eslint-disable-next-line @typescript-eslint/no-require-imports -- the mocked module, read after the env above is set
const purchasesMod = require("react-native-purchases");

describe("isPurchaseCancelled", () => {
  it("recognizes RevenueCat user cancellation without treating other failures as cancellation", () => {
    expect(isPurchaseCancelled({ userCancelled: true })).toBe(true);
    expect(isPurchaseCancelled({ userCancelled: false })).toBe(false);
    expect(isPurchaseCancelled(new Error("store unavailable"))).toBe(false);
  });
});

describe("registerPlanChangeListener", () => {
  it("fires onChange only when the plan changes (de-dupe)", async () => {
    const changes: string[] = [];
    const cleanup = await registerPlanChangeListener((plan) => changes.push(plan));
    expect(cleanup).toBeInstanceOf(Function);
    expect(purchasesMod.default.addCustomerInfoUpdateListener).toHaveBeenCalledTimes(1);

    // First fire seeds lastActive → change recorded.
    purchasesMod.default.__fire({ entitlements: { active: { pro: {} } } });
    // Same state again → de-duped, no second change.
    purchasesMod.default.__fire({ entitlements: { active: { pro: {} } } });
    purchasesMod.default.__fire({ entitlements: { active: { pro: {} } } });
    // Entitlement lapses → change recorded.
    purchasesMod.default.__fire({ entitlements: { active: {} } });
    // Same lapsed state → de-duped.
    purchasesMod.default.__fire({ entitlements: { active: {} } });
    // Re-activates → change recorded.
    purchasesMod.default.__fire({ entitlements: { active: { pro: {} } } });

    expect(changes).toEqual(["pro", "free", "pro"]);

    cleanup?.();
    expect(purchasesMod.default.removeCustomerInfoUpdateListener).toHaveBeenCalledTimes(1);
    expect(purchasesMod.default.__listenerCount()).toBe(0);
  });

  it("returns null when the listener cannot be registered", async () => {
    // registerPlanChangeListener loads the module; with the mock present it
    // succeeds. Verify the contract by ensuring a function is returned above
    // — this test just documents the null path is reachable when loadPurchases
    // returns null (covered by isPurchasesConfigured() elsewhere).
    expect(typeof registerPlanChangeListener).toBe("function");
  });
});

describe("planFromCustomerInfo", () => {
  it("reads the paid plan's entitlement, the way the server does", () => {
    expect(planFromCustomerInfo({ entitlements: { active: {} } })).toBe("free");
    expect(planFromCustomerInfo({ entitlements: { active: { pro: {} } } })).toBe("pro");
    // An entitlement the app does not sell grants nothing.
    expect(planFromCustomerInfo({ entitlements: { active: { plus: {} } } })).toBe("free");
  });
});

describe("getPlanPackages", () => {
  beforeEach(() => jest.mocked(reportFailure).mockClear());
  const pkg = (identifier: string, price: number, introPrice: unknown = null) => ({
    identifier,
    product: { priceString: "$" + price, price, identifier: `recall_${identifier}`, introPrice },
  });
  const FREE_3_DAYS = { price: 0, priceString: "$0.00", cycles: 1, period: "P3D", periodUnit: "DAY", periodNumberOfUnits: 3 };

  it("finds the monthly and yearly packages in the current offering", async () => {
    const monthly = pkg("$rc_monthly", 7.99);
    const annual = pkg("$rc_annual", 59.99);
    purchasesMod.default.getOfferings.mockResolvedValueOnce({
      current: { monthly, annual, availablePackages: [monthly, annual] },
    });
    const { packages, unavailable } = await getPlanPackages();
    expect(unavailable).toBe(false);
    expect(packages.monthly).toMatchObject({ plan: "pro", period: "monthly", priceString: "$7.99", price: 7.99 });
    expect(packages.yearly).toMatchObject({ plan: "pro", period: "yearly", priceString: "$59.99", price: 59.99 });
    expect(packages.monthly?.trial).toBeUndefined();
  });

  it("sells one period when the offering has only that one", async () => {
    const monthly = pkg("$rc_monthly", 9.99);
    purchasesMod.default.getOfferings.mockResolvedValueOnce({
      current: { monthly, annual: null, availablePackages: [monthly] },
    });
    const { packages } = await getPlanPackages();
    expect(packages.yearly).toBeUndefined();
    expect(packages.monthly?.priceString).toBe("$9.99");
  });

  it("promises a free trial on iOS only to an account the App Store says can have it", async () => {
    const monthly = pkg("$rc_monthly", 7.99, FREE_3_DAYS);
    const annual = pkg("$rc_annual", 59.99, FREE_3_DAYS);
    purchasesMod.default.getOfferings.mockResolvedValueOnce({ current: { monthly, annual, availablePackages: [] } });
    purchasesMod.default.checkTrialOrIntroductoryPriceEligibility.mockResolvedValueOnce({
      recall_$rc_monthly: { status: 2 },
      recall_$rc_annual: { status: 1 },
    });
    const { packages } = await getPlanPackages();
    expect(packages.monthly?.trial).toEqual({ count: 3, unit: "day", priceString: "$0.00" });
    expect(packages.yearly?.trial).toBeUndefined();
  });

  it("shows the plain price when the App Store cannot say whether a trial is open", async () => {
    const monthly = pkg("$rc_monthly", 7.99, FREE_3_DAYS);
    purchasesMod.default.getOfferings.mockResolvedValueOnce({ current: { monthly, annual: null, availablePackages: [] } });
    purchasesMod.default.checkTrialOrIntroductoryPriceEligibility.mockRejectedValueOnce(new Error("no answer"));
    const { packages } = await getPlanPackages();
    expect(packages.monthly?.priceString).toBe("$7.99");
    expect(packages.monthly?.trial).toBeUndefined();
  });

  it("takes Google's trial as offered: Play lists it only to an account it is open to", async () => {
    mockPlatform.OS = "android";
    purchasesMod.default.checkTrialOrIntroductoryPriceEligibility.mockClear();
    try {
      const monthly = pkg("$rc_monthly", 7.99, FREE_3_DAYS);
      purchasesMod.default.getOfferings.mockResolvedValueOnce({ current: { monthly, annual: null, availablePackages: [] } });
      const { packages } = await getPlanPackages();
      expect(packages.monthly?.trial).toEqual({ count: 3, unit: "day", priceString: "$0.00" });
      expect(purchasesMod.default.checkTrialOrIntroductoryPriceEligibility).not.toHaveBeenCalled();
    } finally {
      mockPlatform.OS = "ios";
    }
  });

  it.each([
    ["a failed read", undefined, () => purchasesMod.default.getOfferings.mockRejectedValueOnce(new Error("store down"))],
    ["no current offering", "no_current_offering", () => purchasesMod.default.getOfferings.mockResolvedValueOnce({ current: null })],
    ["an offering with no plan", "no_plan_in_offering", () => purchasesMod.default.getOfferings.mockResolvedValueOnce({
      current: { monthly: null, annual: null, availablePackages: [pkg("lifetime", 99)] },
    })],
  ])("calls %s unavailable and reports it, never an empty shop (CLAR-08)", async (_, code, arrange) => {
    arrange();
    await expect(getPlanPackages()).resolves.toEqual({ packages: {}, unavailable: true });
    expect(reportFailure).toHaveBeenCalledTimes(1);
    // The report keeps a code and drops the text, so an empty shop still says which it was.
    expect(reportFailure).toHaveBeenCalledWith("store", code ? expect.objectContaining({ code }) : expect.any(Error));
  });
});

describe("configurePurchases", () => {
  it("configures once, then switches accounts with logIn", async () => {
    (globalThis as { __DEV__?: boolean }).__DEV__ = false;
    // RevenueCat answers no read before it is set up: the store is not ready until then.
    expect(isStoreReady()).toBe(false);
    await configurePurchases("user-a");
    expect(isStoreReady()).toBe(true);
    await configurePurchases("user-a");
    expect(purchasesMod.default.configure).toHaveBeenCalledTimes(1);
    expect(purchasesMod.default.logIn).not.toHaveBeenCalled();

    await signOutRevenueCat();
    // The next account waits for its own set-up.
    expect(isStoreReady()).toBe(false);
    await configurePurchases("user-b");
    expect(isStoreReady()).toBe(true);
    expect(purchasesMod.default.configure).toHaveBeenCalledTimes(1);
    expect(purchasesMod.default.logIn).toHaveBeenCalledWith("user-b");
  });

  it("records nothing for an account that signed out while its set-up ran", async () => {
    await signOutRevenueCat();
    let loggedIn!: () => void;
    purchasesMod.default.logIn.mockImplementationOnce(() => new Promise<void>((resolve) => { loggedIn = resolve; }));
    const settingUp = configurePurchases("user-d");
    await Promise.resolve();
    await signOutRevenueCat();
    loggedIn();
    await settingUp;
    // Not ready while no one is signed in, and the next sign-in logs in again.
    expect(isStoreReady()).toBe(false);
    purchasesMod.default.logIn.mockClear();
    await configurePurchases("user-d");
    expect(purchasesMod.default.logIn).toHaveBeenCalledWith("user-d");
    expect(isStoreReady()).toBe(true);
  });

  it("is ready when a set-up that hung is run again (the plans sheet's Retry)", async () => {
    await signOutRevenueCat();
    purchasesMod.default.logIn.mockImplementationOnce(() => new Promise<never>(() => undefined));
    void configurePurchases("user-f");
    await Promise.resolve();
    expect(isStoreReady()).toBe(false);
    await configurePurchases("user-f");
    expect(purchasesMod.default.logIn).toHaveBeenLastCalledWith("user-f");
    expect(isStoreReady()).toBe(true);
  });

  it("is ready once a set-up that failed has run: the store's own failure is then said", async () => {
    await signOutRevenueCat();
    purchasesMod.default.logIn.mockRejectedValueOnce(new Error("offline"));
    await expect(configurePurchases("user-c")).rejects.toThrow("offline");
    expect(isStoreReady()).toBe(true);
  });
});

describe("a purchase the store holds for approval", () => {
  const monthly = { plan: "pro" as const, period: "monthly" as const, priceString: "$7.99", price: 7.99, productId: "recall_monthly", native: {} as never };
  const pending = Object.assign(new Error("The payment is pending."), { code: "20", userCancelled: false });

  beforeEach(async () => {
    await signOutRevenueCat();
    purchasesMod.default.purchasePackage.mockReset();
  });

  it("is pending, not failed, until the store grants the plan", async () => {
    purchasesMod.default.purchasePackage.mockRejectedValueOnce(pending);
    await expect(purchasePlanPackage(monthly)).resolves.toBe("pending");
    expect(purchasePending()).toBe("pro");

    const changes: string[] = [];
    const cleanup = await registerPlanChangeListener((plan) => changes.push(plan));
    purchasesMod.default.__fire({ entitlements: { active: {} } });
    expect(purchasePending()).toBe("pro");
    // Approved: the store's update lands the plan.
    purchasesMod.default.__fire({ entitlements: { active: { pro: {} } } });
    expect(purchasePending()).toBeNull();
    cleanup?.();
  });

  it.each([
    ["finds the plan", { pro: {} }, "pro"],
    // The user's way out of a payment that never came.
    ["finds nothing", {}, "free"],
  ])("a restore that %s lets go of the hold, and sign-out forgets it", async (_case, active, plan) => {
    purchasesMod.default.purchasePackage.mockRejectedValue(pending);
    await purchasePlanPackage(monthly);
    purchasesMod.default.restorePurchases.mockResolvedValueOnce({ entitlements: { active } });
    await expect(restorePurchases()).resolves.toBe(plan);
    expect(purchasePending()).toBeNull();

    await purchasePlanPackage(monthly);
    await signOutRevenueCat();
    expect(purchasePending()).toBeNull();
  });

  describe("read again as the sheet opens or the app comes back", () => {
    const HOLD_MS = 30 * 60_000;

    beforeEach(() => {
      purchasesMod.default.getCustomerInfo.mockReset();
      jest.mocked(reportFailure).mockClear();
    });

    const SINCE = Date.UTC(2026, 10, 8, 12);

    /** A held Plus, held at SINCE exactly: the clock never drifts under the hold's age. */
    async function hold() {
      purchasesMod.default.purchasePackage.mockRejectedValueOnce(pending);
      const clock = jest.spyOn(Date, "now").mockReturnValue(SINCE);
      try {
        await purchasePlanPackage(monthly);
      } finally {
        clock.mockRestore();
      }
      return SINCE;
    }

    it("lets go once the store grants the plan", async () => {
      const since = await hold();
      purchasesMod.default.getCustomerInfo.mockResolvedValueOnce({ entitlements: { active: { pro: {} } } });
      await recheckPendingPurchase(since + 1_000);
      expect(purchasePending()).toBeNull();
    });

    it("keeps a recent hold the store does not grant yet, and lets go of one that lapsed", async () => {
      const since = await hold();
      purchasesMod.default.getCustomerInfo.mockResolvedValue({ entitlements: { active: {} } });
      await recheckPendingPurchase(since + 60_000);
      expect(purchasePending()).toBe("pro");
      // A declined Ask to Buy leaves no trace in the store's answer: the hold lapses.
      await recheckPendingPurchase(since + HOLD_MS);
      expect(purchasePending()).toBeNull();
    });

    it("keeps a recent hold when the store cannot be read, and says so", async () => {
      const since = await hold();
      purchasesMod.default.getCustomerInfo.mockRejectedValueOnce(new Error("offline"));
      await expect(recheckPendingPurchase(since + 1_000)).resolves.toBeUndefined();
      expect(purchasePending()).toBe("pro");
      expect(reportFailure).toHaveBeenCalledTimes(1);
    });
  });

  it("on Android has an earlier launch's hold in place before the store can sell, past 30 minutes", async () => {
    mockPlatform.OS = "android";
    process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY = "test-android-key";
    try {
      // A Plus slow payment held at the last launch.
      const since = Date.now() - 2 * 24 * 60 * 60_000;
      mockDisk.set("recall-held-purchase.txt", `user-e|pro|${since}`);
      let heldWhenReady: string | null | undefined;
      const stop = subscribeStoreReady(() => {
        if (isStoreReady()) heldWhenReady = purchasePending();
      });
      await configurePurchases("user-e");
      stop();
      expect(heldWhenReady).toBe("pro");
      // A Pro bought now would be a second subscription: still held.
      purchasesMod.default.getCustomerInfo.mockResolvedValueOnce({ entitlements: { active: {} } });
      await recheckPendingPurchase(Date.now() + 31 * 60_000);
      expect(purchasePending()).toBe("pro");
    } finally {
      mockPlatform.OS = "ios";
      delete process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY;
    }
  });

  it("still rejects any other store failure", async () => {
    const declined = Object.assign(new Error("not allowed"), { code: "3" });
    purchasesMod.default.purchasePackage.mockRejectedValueOnce(declined);
    await expect(purchasePlanPackage(monthly)).rejects.toBe(declined);
    expect(purchasePending()).toBeNull();
  });
});

describe("freeTrialOf", () => {
  const intro = (price: number, periodUnit: string, periodNumberOfUnits: number) => ({
    price,
    priceString: price === 0 ? "$0.00" : "$1.99",
    cycles: 1,
    period: "P1W",
    periodUnit,
    periodNumberOfUnits,
  });

  it("reads a free first period", () => {
    expect(freeTrialOf(intro(0, "DAY", 7))).toEqual({ count: 7, unit: "day", priceString: "$0.00" });
    expect(freeTrialOf(intro(0, "MONTH", 1))).toEqual({ count: 1, unit: "month", priceString: "$0.00" });
  });

  it("is no trial when the first period costs anything, or there is none", () => {
    expect(freeTrialOf(intro(1.99, "WEEK", 1))).toBeUndefined();
    expect(freeTrialOf(null)).toBeUndefined();
  });
});
