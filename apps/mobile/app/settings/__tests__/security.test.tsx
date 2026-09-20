import { act, fireEvent, render } from "@testing-library/react-native";

import SecuritySettingsScreen from "@/app/settings/security";

const mockListSessions = jest.fn();

jest.mock("@shopify/flash-list", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  const { View } = jest.requireActual<typeof import("react-native")>("react-native");
  return {
    FlashList: ({
      data,
      renderItem,
      ListEmptyComponent,
      ListFooterComponent,
    }: {
      data: unknown[];
      renderItem: (info: { item: unknown; index: number }) => React.ReactNode;
      ListEmptyComponent?: React.ReactNode;
      ListFooterComponent?: React.ReactNode;
    }) => (
      <View>
        {data.length === 0 ? ListEmptyComponent : null}
        {data.map((item, index) => (
          <View key={index}>{renderItem({ item, index })}</View>
        ))}
        {ListFooterComponent}
      </View>
    ),
  };
});
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
    useRouter: () => ({ replace: jest.fn() }),
    useFocusEffect: (callback: () => void) => React.useEffect(callback, [callback]),
  };
});
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token", signOut: jest.fn() }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/lib/api", () => ({
  api: {
    listSessions: (...args: unknown[]) => mockListSessions(...args),
    revokeSession: jest.fn(),
    logoutAll: jest.fn(),
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
  mockListSessions.mockReset();
});

it("replaces the initial security spinner with the shared settings skeleton", async () => {
  const pending = deferred<{
    sessions: {
      id: string;
      device_label: string;
      platform: string;
      created_at: string;
      last_seen_at: string;
      current: boolean;
    }[];
  }>();
  mockListSessions.mockReturnValueOnce(pending.promise);
  const ui = await render(<SecuritySettingsScreen />);

  expect(ui.getByTestId("settings-loading-skeleton")).toBeTruthy();

  await act(async () => {
    pending.resolve({
      sessions: [{
        id: "current",
        device_label: "This iPhone",
        platform: "ios",
        created_at: "2026-09-19T12:00:00Z",
        last_seen_at: "2026-09-19T12:00:00Z",
        current: true,
      }],
    });
  });
  expect(ui.queryByTestId("settings-loading-skeleton")).toBeNull();
  expect(ui.getByText("This iPhone")).toBeTruthy();
});

it("keeps security load errors distinct and retryable", async () => {
  mockListSessions
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({ sessions: [] });
  const ui = await render(<SecuritySettingsScreen />);

  expect(ui.getByText("common.error")).toBeTruthy();
  expect(ui.queryByTestId("settings-loading-skeleton")).toBeNull();
  await fireEvent.press(ui.getByText("common.retry"));
  expect(mockListSessions).toHaveBeenCalledTimes(2);
});
