import { act, fireEvent, render } from "@testing-library/react-native";

import { UpgradeSheet } from "@/components/UpgradeSheet";

const mockSyncSubscription = jest.fn();
const mockPurchase = jest.fn();
const mockRestore = jest.fn();

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/ui/overlay/Sheet", () => {
  const { View: RNView } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    Sheet: ({ children, visible }: { children: React.ReactNode; visible?: boolean }) =>
      visible ? <RNView>{children}</RNView> : null,
  };
});
jest.mock("@/hooks/useSubscriptionActions", () => ({
  useSubscriptionActions: () => ({
    token: "tok",
    syncSubscription: mockSyncSubscription,
    devUpgrade: jest.fn(),
  }),
}));
jest.mock("@/lib/productAnalytics", () => ({ trackProductEvent: jest.fn() }));
jest.mock("@/lib/purchases", () => ({
  isPurchasesConfigured: () => true,
  isPurchaseCancelled: (error: { userCancelled?: boolean }) => error?.userCancelled === true,
  getMonthlyProPackage: jest.fn(async () => ({ priceString: "$13.99", native: {} })),
  purchaseProPackage: (...args: unknown[]) => mockPurchase(...args),
  restorePurchases: (...args: unknown[]) => mockRestore(...args),
}));

beforeEach(() => {
  mockSyncSubscription.mockReset();
  mockPurchase.mockReset();
  mockRestore.mockReset();
});

it("does not call a paid purchase failed when only the server refresh fails", async () => {
  mockPurchase.mockResolvedValue(true);
  mockSyncSubscription.mockRejectedValue(new Error("503"));
  const onClose = jest.fn();
  const screen = await render(<UpgradeSheet visible onClose={onClose} />);
  await act(async () => {});
  await act(async () => {
    fireEvent.press(screen.getByText("upgrade.subscribe"));
  });
  expect(screen.queryByText("upgrade.purchase_failed")).toBeNull();
  expect(screen.getByText("upgrade.sync_pending")).toBeOnTheScreen();
});

it("shows nothing when the shopper cancels the store sheet", async () => {
  mockPurchase.mockRejectedValue({ userCancelled: true });
  const screen = await render(<UpgradeSheet visible onClose={jest.fn()} />);
  await act(async () => {});
  await act(async () => {
    fireEvent.press(screen.getByText("upgrade.subscribe"));
  });
  expect(screen.queryByText("upgrade.purchase_failed")).toBeNull();
  expect(mockSyncSubscription).not.toHaveBeenCalled();
});
