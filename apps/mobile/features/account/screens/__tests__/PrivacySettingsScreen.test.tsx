import { Alert } from "react-native";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import PrivacySettingsScreen from "@/features/account/screens/PrivacySettingsScreen";

const mockUpdateUser = jest.fn();
const mockLocationLabel = jest.fn();
const mockOpenUrl = jest.fn();
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
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "tok", user: mockUser, updateUser: mockUpdateUser }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/lib/deviceLocation", () => ({
  getDeviceLocationLabel: (...args: unknown[]) => mockLocationLabel(...args),
}));
jest.mock("@/lib/expoRuntime", () => ({ canUseDeviceLocation: () => true }));
jest.mock("@/lib/legalUrls", () => ({
  getLegalPrivacyUrl: () => "https://recall.test/privacy",
}));
jest.mock("@/lib/linkSchemePolicy", () => ({
  openAllowedUrl: (...args: unknown[]) => mockOpenUrl(...args),
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockUser = { name: "bini", location: null, location_enabled: false };
  mockUpdateUser.mockResolvedValue(undefined);
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});

it("shows web search on by default, location, and how data is used", async () => {
  const view = await render(<PrivacySettingsScreen />);
  const search = view.getByRole("switch", { name: "settings.web_search" });
  expect(search.props.accessibilityState.checked).toBe(true);
  expect(view.getByText("settings.web_search_summary")).toBeTruthy();
  expect(view.getByText("settings.location_summary")).toBeTruthy();
  expect(view.getByText("settings.data_use_body")).toBeTruthy();
});

it("turns web search off for the account", async () => {
  const view = await render(<PrivacySettingsScreen />);
  await fireEvent.press(
    view.getByRole("switch", { name: "settings.web_search" }),
  );
  await waitFor(() =>
    expect(mockUpdateUser).toHaveBeenCalledWith({ web_search_enabled: false }),
  );
});

it("turns location on with the device's place", async () => {
  mockLocationLabel.mockResolvedValue("Addis Ababa, Ethiopia");
  const view = await render(<PrivacySettingsScreen />);
  await fireEvent.press(
    view.getByRole("switch", { name: "settings.use_current_location" }),
  );
  await waitFor(() =>
    expect(mockUpdateUser).toHaveBeenCalledWith({
      location_enabled: true,
      location: "Addis Ababa, Ethiopia",
    }),
  );
});

it("opens the privacy policy", async () => {
  const view = await render(<PrivacySettingsScreen />);
  await fireEvent.press(view.getByText("privacy.title"));
  expect(mockOpenUrl).toHaveBeenCalledWith("https://recall.test/privacy");
});
