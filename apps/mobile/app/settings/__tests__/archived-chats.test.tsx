import { act, fireEvent, render } from "@testing-library/react-native";

import ArchivedChatsScreen from "@/app/settings/archived-chats";

const mockListChats = jest.fn();

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ bottom: 0 }),
}));
jest.mock("expo-router", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  return {
    Redirect: () => null,
    useFocusEffect: (callback: () => void) => React.useEffect(callback, [callback]),
  };
});
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token" }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/lib/cache/chatListCache", () => ({
  invalidateChatListCache: jest.fn(),
}));
jest.mock("@/lib/api", () => ({
  api: {
    listChats: (...args: unknown[]) => mockListChats(...args),
    setArchive: jest.fn(),
    deleteChat: jest.fn(),
  },
}));
jest.mock("@/lib/theme", () => ({
  useTheme: () => ({
    bg: "#fff",
    settingsSurface: "#eee",
    border: "#ddd",
    primary: "#00f",
    text: "#111",
    textSecondary: "#555",
    textTertiary: "#777",
    danger: "#f00",
  }),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

beforeEach(() => {
  mockListChats.mockReset();
});

it("uses the settings skeleton only for the initial archived-chat load", async () => {
  const pending = deferred<{ archived: [] }>();
  mockListChats.mockReturnValueOnce(pending.promise);
  const ui = await render(<ArchivedChatsScreen />);

  expect(ui.getByTestId("settings-loading-skeleton")).toBeTruthy();
  expect(ui.queryByText("settings.archived_chats_empty")).toBeNull();

  await act(async () => {
    pending.resolve({ archived: [] });
  });
  expect(ui.queryByTestId("settings-loading-skeleton")).toBeNull();
  expect(ui.getByText("settings.archived_chats_empty")).toBeTruthy();
});

it("keeps archived-chat failures retryable instead of showing an empty state", async () => {
  mockListChats
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({ archived: [] });
  const ui = await render(<ArchivedChatsScreen />);

  expect(ui.getByText("common.error")).toBeTruthy();
  expect(ui.queryByText("settings.archived_chats_empty")).toBeNull();
  await fireEvent.press(ui.getByText("common.retry"));
  expect(mockListChats).toHaveBeenCalledTimes(2);
});
