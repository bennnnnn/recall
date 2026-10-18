import { Alert } from "react-native";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import DataControlsScreen from "@/features/account/screens/DataControlsScreen";

const mockUpdateUser = jest.fn();
const mockLocationLabel = jest.fn();
let mockUser: Record<string, unknown>;

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("expo-router", () => ({
  Redirect: () => null,
  router: { push: jest.fn() },
  useRouter: () => ({ replace: jest.fn() }),
  useNavigation: () => ({ setOptions: jest.fn() }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "tok", user: mockUser, updateUser: mockUpdateUser }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/features/account/hooks/useDataControls", () => ({
  useDataControls: () => ({ progress: "idle", exportData: jest.fn(), deleteAccount: jest.fn() }),
}));
jest.mock("@/lib/api", () => ({ api: { archiveAllChats: jest.fn(), deleteAllChats: jest.fn() } }));
jest.mock("@/lib/cache/chatListCache", () => ({ invalidateChatListCache: jest.fn() }));
jest.mock("@/lib/deviceLocation", () => ({
  getDeviceLocationLabel: (...args: unknown[]) => mockLocationLabel(...args),
}));
jest.mock("@/lib/expoRuntime", () => ({ canUseDeviceLocation: () => true }));
jest.mock("@/ui/controls/StackBackButton", () => ({
  StackBackButton: () => null,
  plainHeaderItems: () => [],
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockUser = { name: "bini", location: null, location_enabled: false };
  mockUpdateUser.mockResolvedValue(undefined);
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});

it("opens with web search (on by default), location and how data is used", async () => {
  const view = await render(<DataControlsScreen />);
  const search = view.getByRole("switch", { name: "settings.web_search" });
  expect(search.props.accessibilityState.checked).toBe(true);
  expect(view.getByText("settings.location_summary")).toBeTruthy();
  expect(view.getByText("settings.data_use_body")).toBeTruthy();
  // The policy itself lives once, under About.
  expect(view.queryByText("privacy.title")).toBeNull();
});

it("turns web search off for the account", async () => {
  const view = await render(<DataControlsScreen />);
  await fireEvent.press(view.getByRole("switch", { name: "settings.web_search" }));
  await waitFor(() => expect(mockUpdateUser).toHaveBeenCalledWith({ web_search_enabled: false }));
});

it("turns location on with the device's place", async () => {
  mockLocationLabel.mockResolvedValue("Addis Ababa, Ethiopia");
  const view = await render(<DataControlsScreen />);
  await fireEvent.press(view.getByRole("switch", { name: "settings.use_current_location" }));
  await waitFor(() =>
    expect(mockUpdateUser).toHaveBeenCalledWith({
      location_enabled: true,
      location: "Addis Ababa, Ethiopia",
    }),
  );
});
