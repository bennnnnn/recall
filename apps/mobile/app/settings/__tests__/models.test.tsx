import { fireEvent, render } from "@testing-library/react-native";

import ModelsSettingsScreen from "@/app/settings/models";

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
    updateUser: jest.fn(),
  }),
}));
jest.mock("@/hooks/useModels", () => ({
  buildModelPreferences: jest.fn(),
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
jest.mock("@/hooks/useTtsPreference", () => ({
  useTtsPreference: () => ({
    ttsModel: "speech-tts-model",
    selectTtsModel: jest.fn(),
  }),
}));
jest.mock("@/hooks/useUsage", () => ({
  useUsage: () => ({
    date: "2026-09-09",
    input_tokens: 8000,
    output_tokens: 4000,
    daily_limit: 100000,
    remaining: 88000,
    context_token_budget: 6000,
    recent_message_window: 20,
  }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/lib/ttsPreference", () => ({
  TTS_DEVICE_MODEL: "device",
  TTS_QUALITY_MODEL: "speech-tts-model",
}));
jest.mock("@/components/UpgradeSheet", () => ({
  UpgradeSheet: () => null,
}));

describe("models settings", () => {
  it("hides token split, prompt window, and p50 until Advanced is opened", async () => {
    const { getByText, queryByText } = await render(<ModelsSettingsScreen />);

    expect(getByText("settings.usage_today")).toBeTruthy();
    expect(queryByText("settings.usage_split")).toBeNull();
    expect(queryByText("settings.prompt_window")).toBeNull();
    expect(queryByText("settings.model_latency")).toBeNull();
    expect(getByText("settings.tts_cloud")).toBeTruthy();

    await fireEvent.press(getByText("settings.advanced"));

    expect(getByText("settings.usage_split")).toBeTruthy();
    expect(getByText("settings.prompt_window")).toBeTruthy();
    expect(getByText("settings.model_latency")).toBeTruthy();
  });
});
