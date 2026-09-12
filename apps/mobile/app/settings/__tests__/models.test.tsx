import { fireEvent, render } from "@testing-library/react-native";

import ModelsSettingsScreen from "@/app/settings/models";

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
  useFocusEffect: (cb: () => void) => cb(),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    token: "tok",
    user: { name: "bini" },
    updateUser: mockUpdateUser,
  }),
}));
jest.mock("@/hooks/useModels", () => ({
  buildModelPreferences: () => ["free-chat"],
  useModels: () => ({
    models: [
      {
        id: "free-chat",
        label: "Flash",
        description: "",
        tier: "flash",
        plan_access: "free",
        available: true,
        input_price_per_m: 0,
        output_price_per_m: 0,
        quota_multiplier: 1,
        healthy: true,
        latency_p50_ms: 1214,
      },
    ],
    isPro: true,
    autoEnabled: true,
    modelEnabledSet: new Set(["free-chat"]),
  }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/components/UpgradeSheet", () => ({
  UpgradeSheet: () => null,
}));

describe("models settings", () => {
  beforeEach(() => {
    mockUpdateUser.mockReset().mockResolvedValue(undefined);
  });

  it("keeps model controls without Usage or Advanced diagnostics", async () => {
    const { getByText, queryByText } = await render(<ModelsSettingsScreen />);

    expect(getByText("settings.model_auto")).toBeTruthy();
    expect(getByText("Flash")).toBeTruthy();
    expect(queryByText("settings.usage_daily")).toBeNull();
    expect(queryByText("settings.usage_group")).toBeNull();
    expect(queryByText("settings.advanced")).toBeNull();
    expect(queryByText("settings.usage_split")).toBeNull();
    expect(queryByText("settings.prompt_window")).toBeNull();
    expect(queryByText("settings.model_latency")).toBeNull();
  });

  it("still saves model preferences when Auto is toggled", async () => {
    const { getByText } = await render(<ModelsSettingsScreen />);
    await fireEvent.press(getByText("settings.model_auto"));
    expect(mockUpdateUser).toHaveBeenCalledWith({ enabled_models: ["free-chat"] });
  });
});
