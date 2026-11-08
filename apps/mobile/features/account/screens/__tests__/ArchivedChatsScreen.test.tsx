import { act, fireEvent, render } from "@testing-library/react-native";
import { Alert } from "react-native";

import ArchivedChatsScreen from "@/features/account/screens/ArchivedChatsScreen";
import { forgetDeletedChat } from "@/features/chat/model/chatListCache";

const mockListChats = jest.fn();
const mockDeleteChat = jest.fn();
const mockDestructive = jest.fn();

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
// The drawer's chat list cache, as its contract reads: the list, or the error.
const mockMoreArchived = jest.fn();
// The shared FlashList double drops onEndReached; this one keeps it to call.
let mockEndReached: (() => void) | undefined;
jest.mock("@shopify/flash-list", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  return {
    FlashList: (props: {
      data: unknown[];
      renderItem: (args: { item: unknown; index: number }) => React.ReactNode;
      keyExtractor: (item: unknown, index: number) => string;
      onEndReached?: () => void;
    }) => {
      mockEndReached = props.onEndReached;
      return React.createElement(
        React.Fragment,
        null,
        ...props.data.map((item, index) =>
          React.createElement(
            React.Fragment,
            { key: props.keyExtractor(item, index) },
            props.renderItem({ item, index }),
          ),
        ),
      );
    },
  };
});
jest.mock("@/features/chat/model/chatListCache", () => ({
  invalidateChatListCache: jest.fn(),
  forgetDeletedChat: jest.fn(),
  fetchMoreArchivedChats: (...args: unknown[]) => mockMoreArchived(...args),
  fetchChatList: async (...args: unknown[]) => {
    try {
      return { data: await mockListChats(...args), error: null };
    } catch (error) {
      return { data: null, error };
    }
  },
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
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => ({
    bg: "#fff",
    settingsSurface: "#eee",
    border: "#ddd",
    primary: "#00f",
    text: "#111",
    textSecondary: "#555",
    textTertiary: "#777",
    danger: "#f00",
    // A header button's colours (the row's Unarchive and Delete).
    control: "#eee",
    onMedia: "#fff",
    pressed: "#ddd",
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

  await fireEvent.press(ui.getByLabelText("chat.delete, Archived chat"));
  expect(mockDestructive).not.toHaveBeenCalled();
  const buttons = (Alert.alert as jest.Mock).mock.calls.at(-1)[2];
  const confirm = buttons.find(
    (button: { style?: string }) => button.style === "destructive",
  ).onPress;
  await act(() => { confirm(); });
  expect(mockDestructive).not.toHaveBeenCalled();

  await act(async () => { pending.resolve(); });
  expect(mockDestructive).toHaveBeenCalledTimes(1);
  // Only the deleted chat leaves the drawer and its cache; every other row stays shown.
  expect(forgetDeletedChat).toHaveBeenCalledWith("archived");
});

it("reads archived chats past the first page when the list end is reached", async () => {
  const row = (id: string) => ({
    id,
    title: `Chat ${id}`,
    model: "free-chat",
    pinned: false,
    archived: true,
    created_at: "2026-01-01",
    updated_at: "2026-01-01",
  });
  mockListChats.mockResolvedValue({ archived: [row("a1")], archived_next_cursor: "after-a1" });
  mockMoreArchived.mockResolvedValueOnce({ archived: [row("a1"), row("a2")] });
  const ui = await render(<ArchivedChatsScreen />);
  expect(ui.queryByText("Chat a2")).toBeNull();

  await act(async () => {
    mockEndReached?.();
  });
  expect(mockMoreArchived).toHaveBeenCalledWith("token");
  expect(ui.getByText("Chat a2")).toBeTruthy();
});

it("shows each archived chat as one row with its date, Unarchive and Delete its own buttons", async () => {
  const { api } = jest.requireMock<{ api: { setArchive: jest.Mock } }>("@/lib/api");
  api.setArchive.mockResolvedValue(undefined);
  mockListChats.mockResolvedValue({
    archived: [
      {
        id: "trip",
        title: "Seattle weather forecast",
        model: "free-chat",
        pinned: false,
        archived: true,
        created_at: "2026-11-07T10:00:00Z",
        updated_at: "2026-11-07T10:00:00Z",
      },
    ],
  });
  const ui = await render(<ArchivedChatsScreen />);

  expect(ui.getByText("Seattle weather forecast")).toBeTruthy();
  expect(ui.getByText(/Nov \d+, 2026/)).toBeTruthy();
  // The actions are buttons named for the chat, not a subtitle and a second row.
  expect(ui.queryByText("chat.unarchive")).toBeNull();
  expect(ui.queryByText("chat.delete")).toBeNull();

  await fireEvent.press(ui.getByLabelText("chat.unarchive, Seattle weather forecast"));
  expect(api.setArchive).toHaveBeenCalledWith("token", "trip", false);
  expect(ui.getByText("settings.archived_chats_empty")).toBeTruthy();
});
