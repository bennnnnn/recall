import { act, fireEvent, render } from "@testing-library/react-native";

import { UpgradeSheet } from "@/features/billing/components/UpgradeSheet";
import { getPlanPackages } from "@/features/billing/model/purchases";
import { reportFailure } from "@/lib/sentry";

const mockSyncSubscription = jest.fn();
const mockSetUpStore = jest.fn(async () => undefined);
const mockRecheck = jest.fn(async () => undefined);
const mockPurchase = jest.fn();
const mockRestore = jest.fn();
let mockPurchasesConfigured = true;
// The store's set-up and a purchase held for approval, as purchases.ts keeps them.
const mockStoreReady = { value: true, listeners: new Set<() => void>() };
const mockPending = { value: null as string | null, listeners: new Set<() => void>() };
function setMockStore(store: { value: unknown; listeners: Set<() => void> }, value: unknown) {
  store.value = value;
  store.listeners.forEach((listener) => listener());
}
const mockTrack = jest.fn();
let mockUser: { plan: string } = { plan: "free" };

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options ? `${key} ${JSON.stringify(options)}` : key,
  }),
}));
jest.mock("@/ui/overlay/FullScreenModal", () => {
  const { View: RNView } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    FullScreenModal: ({ children, visible }: { children: React.ReactNode; visible?: boolean }) =>
      visible ? <RNView>{children}</RNView> : null,
  };
});
// One object, as the provider keeps it.
const mockAccountSession = { account: "user-1:0", getToken: () => "tok" };
jest.mock("@/contexts/accountSession", () => ({
  useAccountSession: () => mockAccountSession,
}));
jest.mock("@/features/billing/hooks/useSubscriptionActions", () => ({
  useSubscriptionActions: () => ({
    token: "tok",
    user: mockUser,
    syncSubscription: mockSyncSubscription,
    devUpgrade: jest.fn(),
    setUpStore: mockSetUpStore,
  }),
}));
jest.mock("@/lib/sentry", () => ({ reportFailure: jest.fn() }));
jest.mock("@/lib/productAnalytics", () => ({
  trackProductEvent: (...args: unknown[]) => mockTrack(...args),
}));
jest.mock("@/features/billing/model/purchases", () => ({
  isPurchasesConfigured: () => mockPurchasesConfigured,
  isPurchaseCancelled: (error: { userCancelled?: boolean }) => error?.userCancelled === true,
  BILLING_PERIODS: ["monthly", "yearly"],
  getPlanPackages: jest.fn(async () => ({
    packages: {
      monthly: { plan: "pro", period: "monthly", priceString: "$7.99", price: 7.99, productId: "recall_monthly", native: {} },
      yearly: { plan: "pro", period: "yearly", priceString: "$59.99", price: 59.99, productId: "recall_yearly", native: {} },
    },
    unavailable: false,
  })),
  purchasePlanPackage: (...args: unknown[]) => mockPurchase(...args),
  restorePurchases: (...args: unknown[]) => mockRestore(...args),
  isStoreReady: () => mockStoreReady.value,
  subscribeStoreReady: (listener: () => void) => {
    mockStoreReady.listeners.add(listener);
    return () => mockStoreReady.listeners.delete(listener);
  },
  recheckPendingPurchase: () => mockRecheck(),
}));
const mockCanRemind = jest.fn(async () => true);
const mockRemind = jest.fn(async () => true);
jest.mock("@/features/billing/model/trialReminder", () => ({
  canRemindTrialEnd: () => mockCanRemind(),
  remindBeforeTrialEnds: (...args: unknown[]) => mockRemind(...(args as [])),
}));
jest.mock("@/features/billing/model/heldPurchase", () => ({
  heldPurchase: () => mockPending.value,
  subscribeHeldPurchase: (listener: () => void) => {
    mockPending.listeners.add(listener);
    return () => mockPending.listeners.delete(listener);
  },
}));

type Screen = Awaited<ReturnType<typeof openSheet>>;

async function pick(screen: Screen, period: "monthly" | "yearly") {
  await act(async () => {
    fireEvent.press(screen.getByTestId(`upgrade-period-${period}`));
  });
}

/** Presses the page's one buy button, for the period picked (yearly to start). */
async function buy(screen: Screen) {
  await act(async () => {
    fireEvent.press(screen.getByTestId("upgrade-subscribe"));
  });
}

async function openSheet(source: "live_talk" | "welcome" | "nudge" | "settings" = "live_talk", onClose = jest.fn()) {
  const screen = await render(<UpgradeSheet visible onClose={onClose} source={source} />);
  await act(async () => {});
  return screen;
}

beforeEach(() => {
  mockSyncSubscription.mockReset();
  mockPurchase.mockReset();
  mockRestore.mockReset();
  mockTrack.mockReset();
  mockPurchasesConfigured = true;
  mockStoreReady.value = true;
  mockPending.value = null;
  mockSetUpStore.mockClear();
  mockRecheck.mockClear();
  mockCanRemind.mockClear().mockResolvedValue(true);
  mockRemind.mockClear();
  jest.mocked(getPlanPackages).mockClear();
  jest.mocked(reportFailure).mockClear();
  mockUser = { plan: "free" };
});

it("offers free users the one plan, yearly first, with the store's prices and what a year saves", async () => {
  const screen = await openSheet();
  // 59.99 against 12 × 7.99 = 95.88: 37.4% less, said as 37 (never rounded up).
  expect(screen.getByText('upgrade.period_yearly_save {"percent":37}')).toBeOnTheScreen();
  expect(screen.getByTestId("upgrade-period-yearly").props.accessibilityState.checked).toBe(true);
  expect(screen.getAllByText("$59.99").length).toBeGreaterThan(0);
  expect(screen.getByText('upgrade.subscribe_price {"plan":"plans.pro","price":"$59.99upgrade.per_year_suffix"}')).toBeOnTheScreen();
  expect(screen.getByText("upgrade.renews_yearly")).toBeOnTheScreen();
  await pick(screen, "monthly");
  expect(screen.getAllByText("$7.99").length).toBeGreaterThan(0);
  expect(screen.getByText('upgrade.subscribe_price {"plan":"plans.pro","price":"$7.99upgrade.per_month_suffix"}')).toBeOnTheScreen();
  expect(screen.getByText("upgrade.renews_monthly")).toBeOnTheScreen();
  expect(mockTrack).toHaveBeenCalledWith("paywall_viewed", { source: "live_talk" });
});

it("names no saving when a year costs no less than twelve months", async () => {
  jest.mocked(getPlanPackages).mockResolvedValueOnce({
    packages: {
      monthly: { plan: "pro", period: "monthly", priceString: "$5", price: 5, productId: "m", native: {} as never },
      yearly: { plan: "pro", period: "yearly", priceString: "$60", price: 60, productId: "y", native: {} as never },
    },
    unavailable: false,
  });
  const screen = await openSheet();
  expect(screen.getByText("upgrade.period_yearly")).toBeOnTheScreen();
  expect(screen.queryByText(/upgrade\.period_yearly_save/)).toBeNull();
});

it("shows no period switch when the store sells one period", async () => {
  jest.mocked(getPlanPackages).mockResolvedValueOnce({
    packages: { monthly: { plan: "pro", period: "monthly", priceString: "$7.99", price: 7.99, productId: "m", native: {} as never } },
    unavailable: false,
  });
  const screen = await openSheet();
  expect(screen.queryByTestId("upgrade-period")).toBeNull();
  expect(screen.getByText("upgrade.renews_monthly")).toBeOnTheScreen();
});

it("says the store is unavailable, never an empty shop, and reads it again on Retry (CLAR-08)", async () => {
  jest.mocked(getPlanPackages).mockResolvedValueOnce({ packages: {}, unavailable: true });
  const screen = await openSheet();
  expect(screen.getByText("upgrade.store_unavailable")).toBeOnTheScreen();
  await act(async () => {
    fireEvent.press(screen.getByText("common.retry"));
  });
  expect(getPlanPackages).toHaveBeenCalledTimes(2);
  expect(screen.queryByText("upgrade.store_unavailable")).toBeNull();
  expect(screen.getAllByText("$59.99").length).toBeGreaterThan(0);
});

it("shows a subscriber their plan, with nothing to buy and no Continue with Free", async () => {
  mockUser = { plan: "pro" };
  const screen = await openSheet("welcome");
  expect(screen.getByText('upgrade.current_plan {"plan":"plans.pro"}')).toBeOnTheScreen();
  expect(screen.queryByTestId("upgrade-subscribe")).toBeNull();
  expect(screen.queryByTestId("upgrade-period")).toBeNull();
  expect(screen.queryByTestId("upgrade-continue-free")).toBeNull();
  // Restore stays: a subscriber on a new phone finds their purchase there.
  expect(screen.getByText("upgrade.restore")).toBeOnTheScreen();
});

it("buys the picked period, then asks the server to re-read the store", async () => {
  mockPurchase.mockResolvedValue("pro");
  mockSyncSubscription.mockResolvedValue(true);
  const screen = await openSheet();
  await pick(screen, "monthly");
  await buy(screen);
  expect(mockPurchase.mock.calls[0][0].period).toBe("monthly");
  expect(mockSyncSubscription).toHaveBeenCalledTimes(1);
  expect(mockTrack).toHaveBeenCalledWith("purchase_succeeded", { plan: "pro" });
});

it("does not call a paid purchase failed when only the server refresh fails", async () => {
  mockPurchase.mockResolvedValue("pro");
  mockSyncSubscription.mockRejectedValue(new Error("503"));
  const screen = await openSheet();
  await buy(screen);
  expect(screen.queryByText("upgrade.purchase_failed")).toBeNull();
  expect(screen.getByText("upgrade.sync_pending")).toBeOnTheScreen();
  expect(reportFailure).toHaveBeenCalledWith("purchase_sync", expect.any(Error));
});

it("reports a store purchase that failed, but not one the shopper cancelled", async () => {
  const failure = Object.assign(new Error("store said no"), { code: "PURCHASE_NOT_ALLOWED" });
  mockPurchase.mockRejectedValueOnce(failure).mockRejectedValueOnce({ userCancelled: true });
  const screen = await openSheet();
  await buy(screen);
  expect(screen.getByText("upgrade.purchase_failed")).toBeOnTheScreen();
  await buy(screen);
  expect(reportFailure).toHaveBeenCalledTimes(1);
  expect(reportFailure).toHaveBeenCalledWith("purchase", failure);
});

it("never unlocks on the client when the store did not grant the plan", async () => {
  mockPurchase.mockResolvedValue("free");
  const screen = await openSheet();
  await buy(screen);
  expect(screen.getByText("upgrade.purchase_failed")).toBeOnTheScreen();
  expect(mockSyncSubscription).not.toHaveBeenCalled();
});

it("shows nothing when the shopper cancels the store sheet", async () => {
  mockPurchase.mockRejectedValue({ userCancelled: true });
  const screen = await openSheet();
  await buy(screen);
  expect(screen.queryByText("upgrade.purchase_failed")).toBeNull();
  expect(mockSyncSubscription).not.toHaveBeenCalled();
  expect(mockTrack).toHaveBeenCalledWith("purchase_failed", { plan: "pro", reason: "cancelled" });
});

it("reports a restore that failed", async () => {
  const failure = new Error("restore failed");
  mockRestore.mockRejectedValue(failure);
  const screen = await openSheet();
  await act(async () => {
    fireEvent.press(screen.getByText("upgrade.restore"));
  });
  expect(screen.getByText("upgrade.purchase_failed")).toBeOnTheScreen();
  expect(reportFailure).toHaveBeenCalledWith("purchase_restore", failure);
});

it("restore with nothing to restore says so and keeps the plan", async () => {
  mockRestore.mockResolvedValue("free");
  const screen = await openSheet();
  await act(async () => {
    fireEvent.press(screen.getByText("upgrade.restore"));
  });
  expect(screen.getByText("upgrade.restore_empty")).toBeOnTheScreen();
  expect(mockSyncSubscription).not.toHaveBeenCalled();
});

it("restore that finds a plan refreshes the server plan", async () => {
  mockRestore.mockResolvedValue("pro");
  mockSyncSubscription.mockResolvedValue(true);
  const screen = await openSheet();
  await act(async () => {
    fireEvent.press(screen.getByText("upgrade.restore"));
  });
  expect(mockSyncSubscription).toHaveBeenCalledTimes(1);
});

it("sells what the plan helps with, never a count or a model's name", async () => {
  const screen = await openSheet();
  expect(screen.getByText('upgrade.plan_title {"plan":"plans.pro"}')).toBeOnTheScreen();
  for (const name of ["chat", "maths", "physics", "chemistry", "calculator", "images", "transcription", "pdf", "scanner"]) {
    expect(screen.getByText(`upgrade.benefit_${name}`)).toBeOnTheScreen();
  }
  // "Web search" is the setting's own words, one key in every language.
  expect(screen.getByText("settings.web_search")).toBeOnTheScreen();
  expect(screen.queryByText(/model/i)).toBeNull();
});

it("says purchases are not in this build instead of a button that does nothing", async () => {
  mockPurchasesConfigured = false;
  const screen = await openSheet();
  expect(screen.getByText("upgrade.store_not_in_build")).toBeOnTheScreen();
  expect(screen.queryByText("upgrade.restore")).toBeNull();
});

it("shows a development build example prices, said to be examples, so the page can be seen whole", async () => {
  mockPurchasesConfigured = false;
  const screen = await openSheet();
  expect(screen.getByText("upgrade.dev_example_prices")).toBeOnTheScreen();
  expect(screen.getByText('upgrade.period_yearly_save {"percent":37}')).toBeOnTheScreen();
  expect(screen.getByText('upgrade.trial_day {"count":3}')).toBeOnTheScreen();
  // It still cannot sell: the button is the development switch, never a store purchase.
  expect(screen.queryByTestId("upgrade-subscribe")).toBeNull();
  expect(getPlanPackages).not.toHaveBeenCalled();
});

it("after the first sign-in offers Free as a choice, kept with one tap", async () => {
  const onClose = jest.fn();
  const screen = await openSheet("welcome", onClose);
  expect(mockTrack).toHaveBeenCalledWith("paywall_viewed", { source: "welcome" });
  await act(async () => {
    fireEvent.press(screen.getByTestId("upgrade-continue-free"));
  });
  expect(onClose).toHaveBeenCalled();
});

it("a nudge to a free account also keeps Free one tap away", async () => {
  const screen = await openSheet("nudge");
  expect(screen.getByTestId("upgrade-continue-free")).toBeOnTheScreen();
  expect(mockTrack).toHaveBeenCalledWith("paywall_viewed", { source: "nudge" });
});

it("closes from the cross", async () => {
  const onClose = jest.fn();
  const screen = await openSheet("settings", onClose);
  fireEvent.press(screen.getByTestId("upgrade-close"));
  expect(onClose).toHaveBeenCalled();
});

it("waits for the store to be set up before reading it, never saying it is unavailable", async () => {
  mockStoreReady.value = false;
  const screen = await openSheet();
  expect(getPlanPackages).not.toHaveBeenCalled();
  expect(screen.queryByText("upgrade.store_unavailable")).toBeNull();
  expect(screen.getByTestId("upgrade-subscribe").props.accessibilityState.busy).toBe(true);
  await act(async () => {
    setMockStore(mockStoreReady, true);
  });
  expect(getPlanPackages).toHaveBeenCalledTimes(1);
  expect(screen.getAllByText("$59.99").length).toBeGreaterThan(0);
});

it("says the store is unavailable when its set-up never came, and Retry sets it up again", async () => {
  // /auth/me failed at launch, or the set-up hung: the store has not been set up.
  jest.useFakeTimers();
  try {
    mockStoreReady.value = false;
    const screen = await openSheet();
    expect(screen.queryByText("upgrade.store_unavailable")).toBeNull();
    await act(async () => {
      jest.advanceTimersByTime(8_000);
    });
    expect(screen.getByText("upgrade.store_unavailable")).toBeOnTheScreen();
    await act(async () => {
      fireEvent.press(screen.getByText("common.retry"));
    });
    expect(mockSetUpStore).toHaveBeenCalledTimes(1);
    // Confirmed: the store is set up and read.
    await act(async () => {
      setMockStore(mockStoreReady, true);
    });
    expect(getPlanPackages).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("upgrade.store_unavailable")).toBeNull();
    expect(screen.getAllByText("$59.99").length).toBeGreaterThan(0);
  } finally {
    jest.useRealTimers();
  }
});

it("reads a held purchase again as the page opens", async () => {
  await openSheet();
  expect(mockRecheck).toHaveBeenCalledTimes(1);
});

it("says a purchase waiting for approval is pending, and offers no second one", async () => {
  mockPurchase.mockImplementation(async () => {
    setMockStore(mockPending, "pro");
    return "pending";
  });
  const screen = await openSheet();
  await buy(screen);
  expect(screen.getByText("upgrade.purchase_pending")).toBeOnTheScreen();
  expect(screen.queryByText("upgrade.purchase_failed")).toBeNull();
  expect(mockTrack).not.toHaveBeenCalledWith("purchase_failed", expect.anything());
  expect(mockSyncSubscription).not.toHaveBeenCalled();
  expect(screen.getByTestId("upgrade-subscribe").props.accessibilityState.disabled).toBe(true);
  // The other period is no way round it: still one purchase.
  await pick(screen, "monthly");
  await buy(screen);
  expect(mockPurchase).toHaveBeenCalledTimes(1);
  // Approved: the store lands the plan and the page sells again.
  await act(async () => {
    setMockStore(mockPending, null);
  });
  expect(screen.queryByText("upgrade.purchase_pending")).toBeNull();
});

it("shows a pending purchase when the page opens again", async () => {
  mockPending.value = "pro";
  const screen = await openSheet();
  expect(screen.getByText("upgrade.purchase_pending")).toBeOnTheScreen();
  await buy(screen);
  expect(mockPurchase).not.toHaveBeenCalled();
});

it("shows today's payment and the renewal's day under the plan", async () => {
  const screen = await openSheet();
  expect(screen.getByText("upgrade.due_today")).toBeOnTheScreen();
  expect(screen.getByText(/^upgrade\.renews_on /)).toBeOnTheScreen();
  expect(screen.queryByText(/upgrade\.start_trial/)).toBeNull();
  expect(screen.queryByText("upgrade.trial_reminder")).toBeNull();
});

const TRIAL_YEAR = {
  packages: {
    yearly: {
      plan: "pro" as const,
      period: "yearly" as const,
      priceString: "$59.99",
      price: 59.99,
      pricePerMonth: "$5.00",
      productId: "recall_yearly",
      native: {} as never,
      trial: { count: 3, unit: "day" as const, priceString: "$0.00" },
    },
  },
  unavailable: false,
};

it("offers a free trial only when the store gives this account one, named by its length", async () => {
  jest.mocked(getPlanPackages).mockResolvedValueOnce(TRIAL_YEAR);
  const screen = await openSheet();
  expect(screen.getByText('upgrade.start_trial_day {"count":3}')).toBeOnTheScreen();
  expect(screen.getByText("$0.00")).toBeOnTheScreen();
  expect(screen.getByText('upgrade.trial_day {"count":3}')).toBeOnTheScreen();
  expect(screen.getByText(/^upgrade\.due_on /)).toBeOnTheScreen();
  expect(screen.getByText("upgrade.trial_reminder")).toBeOnTheScreen();
  // The year's price per month, in the store's own figure.
  expect(screen.getByText('upgrade.per_month_billed_yearly {"price":"$5.00"}')).toBeOnTheScreen();
});

it("promises no reminder where notifications are turned off", async () => {
  jest.mocked(getPlanPackages).mockResolvedValueOnce(TRIAL_YEAR);
  mockCanRemind.mockResolvedValue(false);
  const screen = await openSheet();
  expect(screen.getByText('upgrade.start_trial_day {"count":3}')).toBeOnTheScreen();
  expect(screen.queryByText("upgrade.trial_reminder")).toBeNull();
});

it("sets the reminder as a trial starts, for the day the price is first charged", async () => {
  jest.mocked(getPlanPackages).mockResolvedValueOnce(TRIAL_YEAR);
  mockPurchase.mockResolvedValue("pro");
  mockSyncSubscription.mockResolvedValue(true);
  const before = Date.now();
  const screen = await openSheet();
  await buy(screen);
  expect(mockRemind).toHaveBeenCalledTimes(1);
  const [ends, price] = mockRemind.mock.calls[0] as unknown as [Date, string];
  // Three days from now, give or take a clock change.
  expect(ends.getTime() - before).toBeGreaterThan(3 * 24 * 3600_000 - 2 * 3600_000);
  expect(ends.getTime() - before).toBeLessThan(3 * 24 * 3600_000 + 2 * 3600_000);
  expect(price).toBe("$59.99upgrade.per_year_suffix");
});

it("sets no reminder for a purchase with no trial", async () => {
  mockPurchase.mockResolvedValue("pro");
  mockSyncSubscription.mockResolvedValue(true);
  const screen = await openSheet();
  await buy(screen);
  expect(mockRemind).not.toHaveBeenCalled();
});
