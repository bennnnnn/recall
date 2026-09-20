import { act, fireEvent, render } from "@testing-library/react-native";
import { Alert } from "react-native";

import ArchivedChatsScreen from "@/app/settings/archived-chats";

const mockListChats = jest.fn();
const mockDeleteChat = jest.fn();
const mockDestructive = jest.fn();

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
    deleteChat: (...args: unknown[]) => mockDeleteChat(...args),
  },
}));
jest.mock("@/lib/haptics", () => ({
  ...jest.requireActual("@/lib/haptics"),
  notifyDestructive: (...args: unknown[]) => mockDestructive(...args),
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
  jest.clearAllMocks();
  mockListChats.mockReset();
  mockDeleteChat.mockReset();
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});
afterEach(() => jest.restoreAllMocks());

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

it("haptics only after confirmed archived-chat deletion succeeds", async () => {
  const chat = {
    id: "archived",
    title: "Archived chat",
    model: "free-chat",
    pinned: false,
    archived: true,
    created_at: "2026-01-01",
    updated_at: "2026-01-01",
  };
  const pending = deferred<void>();
  mockListChats.mockResolvedValue({ archived: [chat] });
  mockDeleteChat.mockReturnValue(pending.promise);
  const ui = await render(<ArchivedChatsScreen />);

  await fireEvent.press(ui.getByText("chat.delete"));
  expect(mockDestructive).not.toHaveBeenCalled();
  const buttons = (Alert.alert as jest.Mock).mock.calls.at(-1)[2];
  const confirm = buttons.find(
    (button: { style?: string }) => button.style === "destructive",
  ).onPress;
  await act(() => { confirm(); });
  expect(mockDestructive).not.toHaveBeenCalled();

  await act(async () => { pending.resolve(); });
  expect(mockDestructive).toHaveBeenCalledTimes(1);
});
