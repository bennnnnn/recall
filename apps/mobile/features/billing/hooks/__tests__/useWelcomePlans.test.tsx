import { act, renderHook } from "@testing-library/react-native";

import { useWelcomePlans } from "@/features/billing/hooks/useWelcomePlans";
import { takeOutOfCreditOffer, takePlansOffer } from "@/features/billing/model/welcomePlans";
import type { User } from "@/lib/api/types";

// The launch cache paints every plan "free" (lib/cachedUser.ts): a Plus or Pro account got
// the day's plans sheet before /auth/me answered, and a free one "store unavailable" before
// RevenueCat was set up.

let mockProfileValidated = false;
jest.mock("@/contexts/AuthContext", () => ({
  useAuthOptional: () => ({ profileValidated: mockProfileValidated }),
}));

const mockStore = { ready: false, listeners: new Set<() => void>() };
jest.mock("@/features/billing/model/purchases", () => ({
  isStoreReady: () => mockStore.ready,
  subscribeStoreReady: (listener: () => void) => {
    mockStore.listeners.add(listener);
    return () => mockStore.listeners.delete(listener);
  },
}));

jest.mock("@/features/billing/model/welcomePlans", () => ({
  takePlansOffer: jest.fn(async () => "nudge"),
  takeOutOfCreditOffer: jest.fn(async () => true),
}));

const cachedPro = { id: "u1", plan: "free" } as User;
const freeUser = { id: "u1", plan: "free" } as User;
const proUser = { id: "u1", plan: "pro" } as User;

function setStoreReady(ready: boolean) {
  mockStore.ready = ready;
  mockStore.listeners.forEach((listener) => listener());
}

async function mountHook(user: User, outOfCredit = false) {
  const open = jest.fn();
  const hook = await renderHook(
    (props: { user: User; outOfCredit: boolean }) =>
      useWelcomePlans({ user: props.user, busy: false, outOfCredit: props.outOfCredit, open }),
    { initialProps: { user, outOfCredit } },
  );
  await act(async () => {});
  return { open, hook };
}

beforeEach(() => {
  jest.clearAllMocks();
  mockProfileValidated = false;
  mockStore.ready = false;
  mockStore.listeners.clear();
});

it("offers nothing on the launch cache's plan, before the server has said it", async () => {
  mockStore.ready = true;
  const { open } = await mountHook(cachedPro, true);
  expect(takePlansOffer).not.toHaveBeenCalled();
  expect(takeOutOfCreditOffer).not.toHaveBeenCalled();
  expect(open).not.toHaveBeenCalled();
});

it("never offers a paid account the plans once the server says its plan", async () => {
  mockStore.ready = true;
  mockProfileValidated = true;
  const { open } = await mountHook(proUser, true);
  expect(takePlansOffer).not.toHaveBeenCalled();
  expect(open).not.toHaveBeenCalled();
});

it("offers a free account the plans only once the store can sell them", async () => {
  mockProfileValidated = true;
  const { open } = await mountHook(freeUser);
  expect(takePlansOffer).not.toHaveBeenCalled();

  await act(async () => {
    setStoreReady(true);
  });
  expect(takePlansOffer).toHaveBeenCalledWith("open");
  expect(open).toHaveBeenCalledWith("nudge");
});

it("offers the plans when a free account's allowance runs out, once both are known", async () => {
  mockProfileValidated = true;
  mockStore.ready = true;
  jest.mocked(takePlansOffer).mockResolvedValue(null);
  const { open, hook } = await mountHook(freeUser);
  await hook.rerender({ user: freeUser, outOfCredit: true });
  await act(async () => {});
  expect(open).toHaveBeenCalledWith("quota");
});
