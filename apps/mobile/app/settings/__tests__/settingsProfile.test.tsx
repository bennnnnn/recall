import type { ReactNode } from "react";
import { fireEvent, render } from "@testing-library/react-native";

import SettingsScreen from "@/app/settings/index";
import ProfileSettingsScreen from "@/app/settings/profile";

const mockPush = jest.fn();

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
    updateUser: jest.fn(),
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
  useAppearance: () => ({ preference: "system" }),
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
    AppSheet: ({ children }: { children: ReactNode }) => <RNView>{children}</RNView>,
  };
});

describe("settings home", () => {
  it("keeps age, country, and job off the root list", async () => {
    const { queryByText, getByText, getByLabelText } = await render(<SettingsScreen />);
    expect(queryByText("settings.age_label")).toBeNull();
    expect(queryByText("settings.job_label")).toBeNull();
    expect(queryByText("settings.profile")).toBeNull();
    expect(getByText("settings.experience")).toBeTruthy();
    expect(getByLabelText("settings.account")).toBeTruthy();
  });

  it("opens Account from the tappable header", async () => {
    const { getByLabelText } = await render(<SettingsScreen />);
    await fireEvent.press(getByLabelText("settings.account"));
    expect(mockPush).toHaveBeenCalledWith("/settings/profile");
  });
});

describe("settings account", () => {
  it("lists account identity, not about-you fields", async () => {
    const { getByText, queryByText } = await render(<ProfileSettingsScreen />);
    expect(getByText("settings.name_label")).toBeTruthy();
    expect(getByText("settings.email")).toBeTruthy();
    expect(getByText("settings.sign_in_method")).toBeTruthy();
    expect(getByText("settings.plan_label")).toBeTruthy();
    expect(queryByText("settings.age_label")).toBeNull();
    expect(queryByText("settings.country_label")).toBeNull();
    expect(queryByText("settings.job_label")).toBeNull();
  });
});
