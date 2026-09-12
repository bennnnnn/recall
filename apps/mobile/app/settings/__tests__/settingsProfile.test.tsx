import type { ReactNode } from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import SettingsScreen from "@/app/settings/index";

const mockPush = jest.fn();
const mockSetPreference = jest.fn();
const mockUpdateUser = jest.fn();

jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("expo-router", () => ({
  Redirect: () => null,
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
  useFocusEffect: (cb: () => void) => cb(),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    token: "tok",
    user: {
      name: "bini",
      email: "dev@recall.local",
      age: 54,
      country: "Ethiopia",
      job: "Ethiopia",
      locale: "en",
      memory_enabled: true,
      push_notifications_enabled: true,
      sign_in_provider: "dev",
    },
    signOut: jest.fn(),
    updateUser: mockUpdateUser,
  }),
}));
jest.mock("@/hooks/useModels", () => ({
  useModels: () => ({
    isPro: true,
    autoEnabled: false,
    modelEnabledSet: new Set(["free-chat"]),
  }),
}));
jest.mock("@/contexts/AppearanceContext", () => ({
  useAppearance: () => ({ preference: "system", setPreference: mockSetPreference }),
}));
jest.mock("@/lib/pushNotifications", () => ({
  getNotificationPermissionGranted: jest.fn(async () => true),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/lib/cache/memoryListCache", () => ({
  prefetchMemories: jest.fn(),
}));
jest.mock("@/lib/cache/integrationStatusCache", () => ({
  getCachedConnectedCount: () => 0,
  fetchIntegrationStatus: jest.fn(async () => null),
  connectedCountFromStatus: () => 0,
}));
jest.mock("@/components/UpgradeSheet", () => ({
  UpgradeSheet: () => null,
}));
jest.mock("@/lib/purchases", () => ({
  restorePurchases: jest.fn(),
}));
jest.mock("@/components/AppSheet", () => {
  const { View: RNView } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    AppSheet: ({ children, visible }: { children: ReactNode; visible: boolean }) =>
      visible ? <RNView>{children}</RNView> : null,
  };
});

describe("settings home", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUpdateUser.mockResolvedValue(undefined);
    mockSetPreference.mockResolvedValue(undefined);
  });

  it("shows account controls directly without making the profile header a menu", async () => {
    const { queryByText, getByText, queryByRole } = await render(<SettingsScreen />);
    expect(queryByText("settings.age_label")).toBeNull();
    expect(queryByText("settings.country_label")).toBeNull();
    expect(queryByText("settings.job_label")).toBeNull();
    expect(queryByText("settings.profile")).toBeNull();
    expect(getByText("settings.experience")).toBeTruthy();
    expect(getByText("settings.account")).toBeTruthy();
    expect(queryByText("settings.name_label")).toBeNull();
    expect(getByText("bini")).toBeTruthy();
    expect(getByText("settings.email")).toBeTruthy();
    expect(getByText("settings.sign_in_method")).toBeTruthy();
    expect(getByText("settings.plan_label")).toBeTruthy();
    expect(getByText("settings.manage_subscription")).toBeTruthy();
    expect(getByText("settings.restore_purchases")).toBeTruthy();
    expect(queryByRole("button", { name: "settings.account" })).toBeNull();
    expect(queryByText("settings.voice")).toBeNull();
  });

  it("edits the name from beneath the profile picture in a popup on Settings", async () => {
    const { getByText, getByDisplayValue, getByLabelText, queryByText } =
      await render(<SettingsScreen />);

    expect(queryByText("settings.your_name")).toBeNull();
    await fireEvent.press(getByText("bini"));
    expect(getByText("settings.your_name")).toBeTruthy();
    await fireEvent.changeText(getByDisplayValue("bini"), "  Bini  ");
    await fireEvent.press(getByLabelText("settings.save"));

    await waitFor(() => expect(mockUpdateUser).toHaveBeenCalledWith({ name: "Bini" }));
    expect(queryByText("settings.your_name")).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("opens and selects Appearance without navigating to another page", async () => {
    const { getByText, getByLabelText, queryByTestId } = await render(<SettingsScreen />);
    expect(queryByTestId("settings-picker-sheet")).toBeNull();

    await fireEvent.press(getByText("settings.appearance"));
    expect(queryByTestId("settings-picker-sheet")).toBeTruthy();
    expect(getByLabelText("settings.appearance_system").props.accessibilityState.selected).toBe(true);
    await fireEvent.press(getByLabelText("settings.appearance_dark"));

    expect(mockSetPreference).toHaveBeenCalledWith("dark");
    expect(queryByTestId("settings-picker-sheet")).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("closes Appearance when choosing the current option", async () => {
    const { getByText, getByLabelText, queryByTestId } = await render(<SettingsScreen />);
    await fireEvent.press(getByText("settings.appearance"));
    await fireEvent.press(getByLabelText("settings.appearance_system"));

    expect(mockSetPreference).not.toHaveBeenCalled();
    expect(queryByTestId("settings-picker-sheet")).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
