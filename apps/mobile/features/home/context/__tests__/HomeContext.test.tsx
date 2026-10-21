import { useLayoutEffect } from "react";
import { act, render, waitFor } from "@testing-library/react-native";

import { HomeProvider, useHome } from "@/features/home/context/HomeContext";
import { api, type HomeScreen } from "@/lib/api";

let mockToken: string | null = "token-a";
let mockUserId: string | null = "account-a";
jest.mock("@/contexts/AuthContext", () => ({
  useAuthOptional: () => ({
    token: mockToken,
    user: mockUserId ? { id: mockUserId, name: "Alex" } : null,
  }),
}));
jest.mock("@/lib/api", () => ({ api: { getHomeScreen: jest.fn() } }));
jest.mock("@/lib/deviceTimezone", () => ({ getDeviceTimezone: () => "UTC" }));
jest.mock("@/features/home/model/homeWelcome", () => ({
  instantHomePlaceholder: () => ({ greeting: "placeholder", subtitle: null, urgent_todos: [], starters: [] }),
}));

const served = (greeting: string): HomeScreen =>
  ({ greeting, subtitle: null, urgent_todos: [], starters: [] }) as HomeScreen;

const shown: (string | undefined)[] = [];
let current: ReturnType<typeof useHome>;
function Probe() {
  const value = useHome();
  useLayoutEffect(() => {
    current = value;
    shown.push(value.screen?.greeting);
  }, [value]);
  return null;
}
function Screen() {
  return <HomeProvider><Probe /></HomeProvider>;
}

beforeEach(() => {
  jest.clearAllMocks();
  shown.length = 0;
  mockToken = "token-a";
  mockUserId = "account-a";
  jest.mocked(api.getHomeScreen).mockResolvedValue(served("Good morning, Alex"));
});

it("keeps the screen when the access token rotates, and reads the new token next time", async () => {
  const ui = await render(<Screen />);
  await waitFor(() => expect(current.screen?.greeting).toBe("Good morning, Alex"));
  expect(api.getHomeScreen).toHaveBeenCalledTimes(1);
  expect(api.getHomeScreen).toHaveBeenCalledWith("token-a", "UTC");

  shown.length = 0;
  mockToken = "token-a-refreshed";
  await ui.rerender(<Screen />);
  await act(async () => {});
  expect(api.getHomeScreen).toHaveBeenCalledTimes(1);
  expect(shown).not.toContain("placeholder");

  await act(async () => {
    await current.refresh({ force: true });
  });
  expect(api.getHomeScreen).toHaveBeenLastCalledWith("token-a-refreshed", "UTC");
});

it("starts over for another account", async () => {
  const ui = await render(<Screen />);
  await waitFor(() => expect(current.screen?.greeting).toBe("Good morning, Alex"));
  jest.mocked(api.getHomeScreen).mockResolvedValue(served("Hello, Sam"));
  mockToken = "token-b";
  mockUserId = "account-b";
  await ui.rerender(<Screen />);
  await waitFor(() => expect(current.screen?.greeting).toBe("Hello, Sam"));
  expect(shown).toContain("placeholder");
  expect(api.getHomeScreen).toHaveBeenLastCalledWith("token-b", "UTC");
});
