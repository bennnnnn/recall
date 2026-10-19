import React from "react";
import { Text } from "react-native";
import { render } from "@testing-library/react-native";

import { useHomeRefreshOnChatFocus } from "@/features/home/hooks/useHomeRefreshOnChatFocus";

// Focus runs the callback the way expo-router does while the screen is focused:
// on mount and again whenever the callback changes.
jest.mock("expo-router", () => ({
  useFocusEffect: (callback: () => void) => {
    const { useEffect } = jest.requireActual<typeof import("react")>("react");
    useEffect(() => callback(), [callback]);
  },
}));
const mockRefresh = jest.fn(async () => {});
let mockHasFetched = false;
jest.mock("@/features/home/context/HomeContext", () => ({
  useHome: () => ({ refresh: mockRefresh, hasFetched: mockHasFetched }),
}));

function Probe({ routeChatId, chatId }: { routeChatId?: string; chatId: string | null }) {
  useHomeRefreshOnChatFocus(routeChatId, chatId);
  return <Text>chat</Text>;
}

beforeEach(() => {
  mockRefresh.mockClear();
  mockHasFetched = false;
});

it("refreshes Home quietly on focus when no thread is open and Home was never fetched", async () => {
  await render(<Probe chatId={null} />);
  expect(mockRefresh).toHaveBeenCalledWith({ silent: true });
});

it.each([
  ["a routed thread", { routeChatId: "chat-1", chatId: null }],
  ["a loaded thread", { routeChatId: undefined, chatId: "chat-1" }],
])("leaves Home alone with %s open", async (_name, props) => {
  await render(<Probe {...props} />);
  expect(mockRefresh).not.toHaveBeenCalled();
});

it("reuses a Home that was already fetched", async () => {
  mockHasFetched = true;
  await render(<Probe chatId={null} />);
  expect(mockRefresh).not.toHaveBeenCalled();
});
