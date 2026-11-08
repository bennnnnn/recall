import { renderHook } from "@testing-library/react-native";

import { useSubscriptionActions } from "@/features/billing/hooks/useSubscriptionActions";
import { configurePurchases } from "@/features/billing/model/purchases";

// The plans sheet's Retry when the store was never set up: an account the server never
// confirmed (a launch offline) is read again; a confirmed one whose set-up hung is set up again.

const mockRefreshUser = jest.fn(async () => undefined);
let mockAuth: { profileValidated: boolean; user: { id: string } | null } = { profileValidated: false, user: null };
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "tok", refreshUser: mockRefreshUser, ...mockAuth }),
}));
jest.mock("@/features/billing/model/purchases", () => ({ configurePurchases: jest.fn(async () => undefined) }));
jest.mock("@/lib/api", () => ({ api: {} }));

beforeEach(() => {
  jest.clearAllMocks();
});

it("reads the account again when the server never confirmed it", async () => {
  mockAuth = { profileValidated: false, user: { id: "user-1" } };
  const { result } = await renderHook(() => useSubscriptionActions());
  await result.current.setUpStore();
  expect(mockRefreshUser).toHaveBeenCalledTimes(1);
  expect(configurePurchases).not.toHaveBeenCalled();
});

it("sets the store up again for a confirmed account whose set-up hung", async () => {
  mockAuth = { profileValidated: true, user: { id: "user-1" } };
  const { result } = await renderHook(() => useSubscriptionActions());
  await result.current.setUpStore();
  expect(configurePurchases).toHaveBeenCalledWith("user-1");
  expect(mockRefreshUser).not.toHaveBeenCalled();
});
