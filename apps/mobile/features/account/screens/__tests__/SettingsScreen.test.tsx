import type { ReactNode } from "react";
import { Alert } from "react-native";
import { act, fireEvent, render, waitFor } from "@testing-library/react-native";

import SettingsScreen from "@/features/account/screens/SettingsScreen";
import { getNotificationPermissionGranted } from "@/lib/pushNotifications";

const mockPush = jest.fn();
const mockReplace = jest.fn();
const mockSetPreference = jest.fn();
const mockSetAccent = jest.fn();
const mockSetHaptics = jest.fn();
const mockUpdateUser = jest.fn();
const mockSignOut = jest.fn();
let mockIsPro = true;

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("expo-router", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  return {
    Redirect: () => null,
    router: { push: (...args: unknown[]) => mockPush(...args) },
    useRouter: () => ({ push: mockPush, replace: mockReplace }),
    useFocusEffect: (cb: () => void) => React.useEffect(cb, [cb]),
  };
});
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    token: "tok",
    user: {
      id: "22222222-2222-4222-8222-222222222222",
      name: "bini",
      email: "dev@recall.local",
      age: 54,
      country: "Ethiopia",
      job: "Ethiopia",
      locale: "en",
      memory_enabled: true,
      push_notifications_enabled: true,
      sign_in_provider: "google",
      tts_voice: "cedar",
    },
    signOut: mockSignOut,
    updateUser: mockUpdateUser,
  }),
}));
jest.mock("@/hooks/useModels", () => ({
  useModels: () => ({
    isPro: mockIsPro,
    autoEnabled: false,
    modelEnabledSet: new Set(["free-chat"]),
  }),
}));
jest.mock("@/contexts/AppearanceContext", () => ({
  useAppearance: () => ({ preference: "system", setPreference: mockSetPreference }),
  useAccent: () => ({ accent: "indigo", setAccent: mockSetAccent }),
  useHaptics: () => ({ enabled: true, setEnabled: mockSetHaptics }),
}));
jest.mock("@/features/account/hooks/useUsage", () => ({
  useUsage: () => ({
    usage: { date: "2026-10-14", daily_limit: 100, remaining: 80, input_tokens: 10, output_tokens: 10 },
  }),
}));
jest.mock("@/lib/pushNotifications", () => ({
  getNotificationPermissionGranted: jest.fn(async () => true),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/features/memory/model/memoryListCache", () => ({
  prefetchMemories: jest.fn(),
}));
jest.mock("@/components/UpgradeSheet", () => ({
  UpgradeSheet: () => null,
}));
jest.mock("@/lib/config", () => ({ getApiUrl: () => "https://api.recall.test" }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0 }));
jest.mock("@/ui/overlay/Sheet", () => {
  const { View: RNView } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    Sheet: ({ children, visible }: { children: ReactNode; visible: boolean }) =>
      visible ? <RNView>{children}</RNView> : null,
  };
});

function confirmLastAlert() {
  const buttons = (Alert.alert as jest.Mock).mock.calls.at(-1)[2];
  return buttons.find((button: { style?: string }) => button.style === "destructive").onPress;
}

describe("settings home", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockIsPro = true;
    mockUpdateUser.mockResolvedValue(undefined);
    mockSetPreference.mockResolvedValue(undefined);
    mockSetAccent.mockResolvedValue(undefined);
    mockSignOut.mockResolvedValue(undefined);
    jest.spyOn(Alert, "alert").mockImplementation(() => {});
  });

  it("shows the account in one group without the profile fields or restore", async () => {
    const { queryByText, getByText } = await render(<SettingsScreen />);
    expect(getByText("bini")).toBeTruthy();
    expect(getByText("dev@recall.local")).toBeTruthy();
    expect(getByText("settings.signed_in_with")).toBeTruthy();
    expect(getByText("settings.manage_subscription")).toBeTruthy();
    expect(getByText("settings.usage_left_pro")).toBeTruthy();
    expect(queryByText("settings.restore_purchases")).toBeNull();
    expect(queryByText("settings.sign_in_method")).toBeNull();
    expect(queryByText("settings.age_label")).toBeNull();
    expect(queryByText("settings.job_label")).toBeNull();
  });

  it("opens the Profile page from the avatar", async () => {
    const { getByLabelText, queryByTestId } = await render(<SettingsScreen />);
    await fireEvent.press(getByLabelText("settings.profile"));
    expect(mockPush).toHaveBeenCalledWith("/settings/profile");
    expect(queryByTestId("settings-profile-sheet")).toBeNull();
  });

  it.each([
    ["settings.personalization", "/settings/preferences"],
    ["settings.model", "/settings/models"],
    ["settings.voice", "/settings/voice"],
    ["settings.notifications", "/settings/notifications"],
    ["settings.help_about", "/settings/about"],
  ])("%s opens %s", async (title, href) => {
    const { getByText } = await render(<SettingsScreen />);
    await fireEvent.press(getByText(title));
    expect(mockPush).toHaveBeenCalledWith(href);
  });

  it("reads the notification permission once per visit", async () => {
    const { findByLabelText } = await render(<SettingsScreen />);
    await findByLabelText("settings.notifications, settings.on");
    expect(getNotificationPermissionGranted).toHaveBeenCalledTimes(1);
  });

  it("shows the chosen voice on the Voice row", async () => {
    const { getByText } = await render(<SettingsScreen />);
    expect(getByText("Cedar")).toBeTruthy();
  });

  it("changes the language from a menu on the main page", async () => {
    const { getByText, getByLabelText, queryByTestId } = await render(<SettingsScreen />);
    await fireEvent.press(getByText("settings.language"));
    expect(queryByTestId("select-menu")).toBeTruthy();
    await fireEvent.press(getByLabelText("Español"));
    await waitFor(() => expect(mockUpdateUser).toHaveBeenCalledWith({ locale: "es" }));
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("turns haptics off on this device", async () => {
    const { getByRole } = await render(<SettingsScreen />);
    await fireEvent.press(getByRole("switch", { name: "settings.haptics" }));
    expect(mockSetHaptics).toHaveBeenCalledWith(false);
  });

  it("asks before signing out", async () => {
    const { getByText } = await render(<SettingsScreen />);
    await fireEvent.press(getByText("settings.sign_out"));
    expect(mockSignOut).not.toHaveBeenCalled();
    await act(async () => { confirmLastAlert()(); });
    await waitFor(() => expect(mockSignOut).toHaveBeenCalledTimes(1));
    expect(mockReplace).toHaveBeenCalledWith("/login");
  });

  it("opens and selects Appearance without navigating to another page", async () => {
    const { getByText, getByLabelText, queryByTestId } = await render(<SettingsScreen />);
    expect(queryByTestId("select-menu")).toBeNull();

    await fireEvent.press(getByText("settings.appearance"));
    expect(queryByTestId("select-menu")).toBeTruthy();
    expect(getByLabelText("settings.appearance_system").props.accessibilityState.checked).toBe(true);
    await fireEvent.press(getByLabelText("settings.appearance_dark"));

    expect(mockSetPreference).toHaveBeenCalledWith("dark");
    expect(queryByTestId("select-menu")).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("opens Accent color with a swatch per preset and applies the pick", async () => {
    const { getByText, getByLabelText, queryByTestId } = await render(<SettingsScreen />);
    await fireEvent.press(getByText("settings.accent"));
    expect(queryByTestId("select-menu")).toBeTruthy();
    expect(getByLabelText("settings.accent_indigo").props.accessibilityState.checked).toBe(true);
    await fireEvent.press(getByLabelText("settings.accent_ocean"));

    expect(mockSetAccent).toHaveBeenCalledWith("ocean");
    expect(queryByTestId("select-menu")).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("closes Appearance when choosing the current option", async () => {
    const { getByText, getByLabelText, queryByTestId } = await render(<SettingsScreen />);
    await fireEvent.press(getByText("settings.appearance"));
    await fireEvent.press(getByLabelText("settings.appearance_system"));

    expect(mockSetPreference).not.toHaveBeenCalled();
    expect(queryByTestId("select-menu")).toBeNull();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("offers the upgrade on a free plan", async () => {
    mockIsPro = false;
    const { getByText, queryByText } = await render(<SettingsScreen />);
    expect(getByText("settings.account_free")).toBeTruthy();
    expect(queryByText("settings.manage_subscription")).toBeNull();
    expect(getByText("settings.usage_left")).toBeTruthy();
  });
});
