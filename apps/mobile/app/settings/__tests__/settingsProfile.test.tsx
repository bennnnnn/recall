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
jest.mock("@/components/AppSheet", () => {
  const { View: RNView } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    AppSheet: ({ children }: { children: ReactNode }) => <RNView>{children}</RNView>,
  };
});

describe("settings home", () => {
  it("keeps age, country, and job off the root list", async () => {
    const { queryByText, getByText } = await render(<SettingsScreen />);
    expect(queryByText("settings.age_label")).toBeNull();
    expect(queryByText("settings.job_label")).toBeNull();
    expect(queryByText("settings.account_label")).toBeNull();
    expect(getByText("settings.profile")).toBeTruthy();
  });

  it("opens profile from the Profile row above App", async () => {
    const { getByText } = await render(<SettingsScreen />);
    await fireEvent.press(getByText("settings.profile"));
    expect(mockPush).toHaveBeenCalledWith("/settings/profile");
  });
});

describe("settings profile", () => {
  it("lists profile fields and names the row Plan, not Account", async () => {
    const { getByText, queryByText } = await render(<ProfileSettingsScreen />);
    expect(getByText("settings.name_label")).toBeTruthy();
    expect(getByText("settings.age_label")).toBeTruthy();
    expect(getByText("settings.country_label")).toBeTruthy();
    expect(getByText("settings.job_label")).toBeTruthy();
    expect(getByText("settings.plan_label")).toBeTruthy();
    expect(queryByText("settings.account_label")).toBeNull();
  });
});
