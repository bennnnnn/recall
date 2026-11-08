import { act, fireEvent, render } from "@testing-library/react-native";

import { UpgradeSheet } from "@/features/billing/components/UpgradeSheet";
import { getPlanPackages } from "@/features/billing/model/purchases";
import { reportFailure } from "@/lib/sentry";

const mockSyncSubscription = jest.fn();
const mockSetUpStore = jest.fn(async () => undefined);
const mockRecheck = jest.fn(async () => undefined);
const mockPurchase = jest.fn();
const mockRestore = jest.fn();
const mockListPlans = jest.fn();
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
jest.mock("@/ui/overlay/Sheet", () => {
  const { View: RNView } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    Sheet: ({ children, visible }: { children: React.ReactNode; visible?: boolean }) =>
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
jest.mock("@/lib/api", () => ({
  api: {
    listPlans: (...args: unknown[]) => mockListPlans(...args),
  },
}));
jest.mock("@/lib/sentry", () => ({ reportFailure: jest.fn() }));
jest.mock("@/lib/productAnalytics", () => ({
  trackProductEvent: (...args: unknown[]) => mockTrack(...args),
}));
jest.mock("@/features/billing/model/purchases", () => ({
  isPurchasesConfigured: () => mockPurchasesConfigured,
  isPurchaseCancelled: (error: { userCancelled?: boolean }) => error?.userCancelled === true,
  getPlanPackages: jest.fn(async () => ({
    packages: {
      plus: { plan: "plus", priceString: "$7.99", productId: "recall_plus", native: {} },
      pro: { plan: "pro", priceString: "$13.99", productId: "recall_pro", native: {} },
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
jest.mock("@/features/billing/model/heldPurchase", () => ({
  heldPurchase: () => mockPending.value,
  subscribeHeldPurchase: (listener: () => void) => {
    mockPending.listeners.add(listener);
    return () => mockPending.listeners.delete(listener);
  },
}));

const CATALOG = {
  current: "free",
  plans: [
    { id: "free", features: ["image_generation"], allowances: { daily_messages: 10, daily_image_generations: 3 } },
    {
      id: "plus",
      features: ["all_models", "image_generation", "speech_transcription", "speech_tts"],
      allowances: { daily_messages: 200, daily_image_generations: 10, monthly_live_talk_minutes: 0 },
    },
    {
      id: "pro",
      features: ["all_models", "image_generation", "speech_transcription", "speech_tts", "live_talk"],
      allowances: { daily_messages: 1000, daily_image_generations: 15, monthly_live_talk_minutes: 60 },
    },
  ],
};

/** Picks a plan's card, then presses the sheet's one buy button. */
async function buy(screen: Awaited<ReturnType<typeof openSheet>>, plan: "plus" | "pro") {
  await act(async () => {
    fireEvent.press(screen.getByTestId(`upgrade-plan-${plan}`));
  });
  await act(async () => {
    fireEvent.press(screen.getByTestId("upgrade-subscribe"));
  });
}

async function openSheet() {
  const screen = await render(<UpgradeSheet visible onClose={jest.fn()} source="live_talk" />);
  await act(async () => {});
  return screen;
}

beforeEach(() => {
  mockSyncSubscription.mockReset();
  mockPurchase.mockReset();
  mockRestore.mockReset();
  mockTrack.mockReset();
  mockListPlans.mockReset().mockResolvedValue(CATALOG);
  mockPurchasesConfigured = true;
  mockStoreReady.value = true;
  mockPending.value = null;
  mockSetUpStore.mockClear();
  mockRecheck.mockClear();
  jest.mocked(getPlanPackages).mockClear();
  jest.mocked(reportFailure).mockClear();
  mockUser = { plan: "free" };
});

it("offers free users both plans with store prices and server numbers", async () => {
  const screen = await openSheet();
  expect(screen.getByTestId("upgrade-plan-plus")).toBeOnTheScreen();
  expect(screen.getByTestId("upgrade-plan-pro")).toBeOnTheScreen();
  expect(screen.getByText(/^\$7\.99/)).toBeOnTheScreen();
  expect(screen.getByText(/^\$13\.99/)).toBeOnTheScreen();
  // The picked plan's list: Plus to start, Pro once its tile is tapped.
  expect(screen.getByText('upgrade.feature_images {"count":10}')).toBeOnTheScreen();
  await act(async () => {
    fireEvent.press(screen.getByTestId("upgrade-plan-pro"));
  });
  expect(screen.getByText('upgrade.feature_live_talk {"count":60}')).toBeOnTheScreen();
  expect(mockTrack).toHaveBeenCalledWith("paywall_viewed", { source: "live_talk" });
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
  expect(screen.getByText(/^\$7\.99/)).toBeOnTheScreen();
});

it("offers a Plus subscriber only the step up to Pro", async () => {
  mockUser = { plan: "plus" };
  const screen = await openSheet();
  expect(screen.queryByTestId("upgrade-plan-plus")).toBeNull();
  expect(screen.getByTestId("upgrade-plan-pro")).toBeOnTheScreen();
  expect(screen.getByText('upgrade.current_plan {"plan":"plans.plus"}')).toBeOnTheScreen();
});

it("buys the chosen plan, then asks the server to re-read the store", async () => {
  mockPurchase.mockResolvedValue("plus");
  mockSyncSubscription.mockResolvedValue(true);
  const screen = await openSheet();
  await buy(screen, "plus");
  expect(mockPurchase.mock.calls[0][0].plan).toBe("plus");
  expect(mockSyncSubscription).toHaveBeenCalledTimes(1);
  expect(mockTrack).toHaveBeenCalledWith("purchase_succeeded", { plan: "plus" });
});

it("does not call a paid purchase failed when only the server refresh fails", async () => {
  mockPurchase.mockResolvedValue("pro");
  mockSyncSubscription.mockRejectedValue(new Error("503"));
  const screen = await openSheet();
  await buy(screen, "pro");
  expect(screen.queryByText("upgrade.purchase_failed")).toBeNull();
  expect(screen.getByText("upgrade.sync_pending")).toBeOnTheScreen();
  expect(reportFailure).toHaveBeenCalledWith("purchase_sync", expect.any(Error));
});

it("reports a store purchase that failed, but not one the shopper cancelled", async () => {
  const failure = Object.assign(new Error("store said no"), { code: "PURCHASE_NOT_ALLOWED" });
  mockPurchase.mockRejectedValueOnce(failure).mockRejectedValueOnce({ userCancelled: true });
  const screen = await openSheet();
  await buy(screen, "plus");
  expect(screen.getByText("upgrade.purchase_failed")).toBeOnTheScreen();
  await buy(screen, "plus");
  expect(reportFailure).toHaveBeenCalledTimes(1);
  expect(reportFailure).toHaveBeenCalledWith("purchase", failure);
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

it("never unlocks on the client when the store did not grant the plan", async () => {
  mockPurchase.mockResolvedValue("plus");
  const screen = await openSheet();
  await buy(screen, "pro");
  expect(screen.getByText("upgrade.purchase_failed")).toBeOnTheScreen();
  expect(mockSyncSubscription).not.toHaveBeenCalled();
});

it("shows nothing when the shopper cancels the store sheet", async () => {
  mockPurchase.mockRejectedValue({ userCancelled: true });
  const screen = await openSheet();
  await buy(screen, "plus");
  expect(screen.queryByText("upgrade.purchase_failed")).toBeNull();
  expect(mockSyncSubscription).not.toHaveBeenCalled();
  expect(mockTrack).toHaveBeenCalledWith("purchase_failed", {
    plan: "plus",
    reason: "cancelled",
  });
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

it("sells what a plan gives, never a model's name", async () => {
  const screen = await openSheet();
  expect(screen.getAllByText('upgrade.free_has {"count":10}').length).toBeGreaterThan(0);
  expect(screen.getByText('upgrade.feature_messages {"count":200}')).toBeOnTheScreen();
  expect(screen.getByText('upgrade.feature_messages {"count":1000}')).toBeOnTheScreen();
  expect(screen.getByText("upgrade.feature_voice")).toBeOnTheScreen();
  await act(async () => {
    fireEvent.press(screen.getByTestId("upgrade-plan-pro"));
  });
  expect(screen.getByText("upgrade.feature_sharper")).toBeOnTheScreen();
  expect(screen.queryByText(/model/i)).toBeNull();
});

it("says purchases are not in this build instead of a button that does nothing", async () => {
  mockPurchasesConfigured = false;
  const screen = await openSheet();
  expect(screen.getByText("upgrade.store_not_in_build")).toBeOnTheScreen();
  expect(screen.queryByText("upgrade.coming_soon")).toBeNull();
  expect(screen.queryByText("upgrade.restore")).toBeNull();
});

it("after the first sign-in offers Free as a choice, kept with one tap", async () => {
  const onClose = jest.fn();
  const screen = await render(<UpgradeSheet visible onClose={onClose} source="welcome" />);
  await act(async () => {});
  expect(screen.getByText("upgrade.welcome_title")).toBeOnTheScreen();
  expect(screen.getByText("upgrade.cancel_anytime")).toBeOnTheScreen();
  expect(mockTrack).toHaveBeenCalledWith("paywall_viewed", { source: "welcome" });
  await act(async () => {
    fireEvent.press(screen.getByTestId("upgrade-continue-free"));
  });
  expect(onClose).toHaveBeenCalled();
});

it("shows a paid account its plan, with no Continue with Free", async () => {
  mockUser = { plan: "plus" };
  const screen = await render(<UpgradeSheet visible onClose={jest.fn()} source="welcome" />);
  await act(async () => {});
  expect(screen.getByText("upgrade.title")).toBeOnTheScreen();
  expect(screen.queryByTestId("upgrade-continue-free")).toBeNull();
});

it("starts on the first plan up and names the picked plan and its price on the one button", async () => {
  const screen = await openSheet();
  expect(screen.getByTestId("upgrade-plan-plus").props.accessibilityState.checked).toBe(true);
  expect(screen.getByText('upgrade.subscribe_for {"plan":"plans.plus","price":"$7.99"}')).toBeOnTheScreen();
  await act(async () => {
    fireEvent.press(screen.getByTestId("upgrade-plan-pro"));
  });
  expect(screen.getByTestId("upgrade-plan-pro").props.accessibilityState.checked).toBe(true);
  expect(screen.getByText('upgrade.subscribe_for {"plan":"plans.pro","price":"$13.99"}')).toBeOnTheScreen();
});

it("a nudge to a free account also keeps Free one tap away", async () => {
  const screen = await render(<UpgradeSheet visible onClose={jest.fn()} source="nudge" />);
  await act(async () => {});
  expect(screen.getByTestId("upgrade-continue-free")).toBeOnTheScreen();
  expect(mockTrack).toHaveBeenCalledWith("paywall_viewed", { source: "nudge" });
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
  expect(screen.getByText('upgrade.subscribe_for {"plan":"plans.plus","price":"$7.99"}')).toBeOnTheScreen();
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
    expect(screen.getByText(/^\$7\.99/)).toBeOnTheScreen();
  } finally {
    jest.useRealTimers();
  }
});

it("reads a held purchase again as the sheet opens", async () => {
  await openSheet();
  expect(mockRecheck).toHaveBeenCalledTimes(1);
});

it("says a purchase waiting for approval is pending, and offers no second one", async () => {
  mockPurchase.mockImplementation(async () => {
    setMockStore(mockPending, "plus");
    return "pending";
  });
  const screen = await openSheet();
  await buy(screen, "plus");
  expect(screen.getByText("upgrade.purchase_pending")).toBeOnTheScreen();
  expect(screen.queryByText("upgrade.purchase_failed")).toBeNull();
  expect(mockTrack).not.toHaveBeenCalledWith("purchase_failed", expect.anything());
  expect(mockSyncSubscription).not.toHaveBeenCalled();
  expect(screen.getByTestId("upgrade-subscribe").props.accessibilityState.disabled).toBe(true);
  await buy(screen, "pro");
  expect(mockPurchase).toHaveBeenCalledTimes(1);
  // Approved: the store lands the plan and the sheet sells again.
  await act(async () => {
    setMockStore(mockPending, null);
  });
  expect(screen.queryByText("upgrade.purchase_pending")).toBeNull();
});

it("shows a pending purchase when the sheet opens again", async () => {
  mockPending.value = "pro";
  const screen = await openSheet();
  expect(screen.getByText("upgrade.purchase_pending")).toBeOnTheScreen();
  await buy(screen, "plus");
  expect(mockPurchase).not.toHaveBeenCalled();
});
