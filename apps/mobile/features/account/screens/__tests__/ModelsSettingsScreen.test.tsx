import { act, fireEvent, render } from "@testing-library/react-native";

import ModelsSettingsScreen from "@/features/account/screens/ModelsSettingsScreen";

const mockUpdateUser = jest.fn();
const mockBuildModelPreferences = jest.fn(
  (auto: boolean, modelIds: Iterable<string>) =>
    auto ? ["auto", ...modelIds] : [...modelIds],
);
let mockIsPro = true;
let mockAutoEnabled = true;
let mockEnabledModelIds = ["free-chat"];
let mockUpgradeVisible = false;
let mockModels = [
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
];

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
  buildModelPreferences: (...args: [boolean, Iterable<string>]) =>
    mockBuildModelPreferences(...args),
  useModels: () => ({
    models: mockModels,
    isPaid: mockIsPro,
    autoEnabled: mockAutoEnabled,
    modelEnabledSet: new Set(mockEnabledModelIds),
  }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/components/UpgradeSheet", () => ({
  UpgradeSheet: ({ visible }: { visible: boolean }) => {
    mockUpgradeVisible = visible;
    return null;
  },
}));

describe("models settings: one choice, Auto or a model", () => {
  beforeEach(() => {
    mockUpdateUser.mockReset().mockResolvedValue(undefined);
    mockBuildModelPreferences.mockClear();
    mockIsPro = true;
    mockAutoEnabled = true;
    mockEnabledModelIds = [];
    mockUpgradeVisible = false;
    mockModels = [
      {
        id: "free-chat",
        label: "Flash",
        description: "Fast everyday answers.",
        tier: "flash",
        plan_access: "free",
        available: true,
        input_price_per_m: 0,
        output_price_per_m: 0,
        quota_multiplier: 1,
        healthy: true,
        latency_p50_ms: 1214,
      },
      {
        id: "smart-chat",
        label: "Luna",
        description: "Strong reasoning for hard questions.",
        tier: "flash",
        plan_access: "pro",
        available: true,
        input_price_per_m: 0,
        output_price_per_m: 0,
        quota_multiplier: 1,
        healthy: true,
        latency_p50_ms: 1214,
      },
    ];
  });

  it("lists Auto and each model with what it is good at", async () => {
    const { getByText } = await render(<ModelsSettingsScreen />);
    expect(getByText("settings.model_auto")).toBeTruthy();
    expect(getByText("settings.model_auto_summary")).toBeTruthy();
    expect(getByText("Flash")).toBeTruthy();
    expect(getByText("Fast everyday answers.")).toBeTruthy();
    expect(getByText("Strong reasoning for hard questions.")).toBeTruthy();
  });

  it("checks Auto when it is on, never a model as well", async () => {
    const { getByRole } = await render(<ModelsSettingsScreen />);
    expect(
      getByRole("button", { name: "settings.model_auto" }).props
        .accessibilityState.selected,
    ).toBe(true);
    expect(
      getByRole("button", { name: "Flash" }).props.accessibilityState.selected,
    ).toBeUndefined();
  });

  it("picking a model saves that one model", async () => {
    const { getByRole } = await render(<ModelsSettingsScreen />);
    await act(async () => {
      fireEvent.press(getByRole("button", { name: "Luna" }));
    });
    expect(mockUpdateUser).toHaveBeenCalledWith({
      enabled_models: ["smart-chat"],
    });
  });

  it("picking Auto saves Auto", async () => {
    mockAutoEnabled = false;
    mockEnabledModelIds = ["smart-chat"];
    const { getByRole } = await render(<ModelsSettingsScreen />);
    expect(
      getByRole("button", { name: "Luna" }).props.accessibilityState.selected,
    ).toBe(true);
    await act(async () => {
      fireEvent.press(getByRole("button", { name: "settings.model_auto" }));
    });
    expect(mockUpdateUser).toHaveBeenCalledWith({ enabled_models: ["auto"] });
  });

  it("a locked model opens the plans instead of saving", async () => {
    mockIsPro = false;
    const { getByRole, getByText } = await render(<ModelsSettingsScreen />);
    expect(getByText("plans.plus")).toBeTruthy();
    await act(async () => {
      fireEvent.press(getByRole("button", { name: "Luna, plans.plus" }));
    });
    expect(mockUpgradeVisible).toBe(true);
    expect(mockUpdateUser).not.toHaveBeenCalled();
  });

  it("marks a degraded model and disables an unavailable one", async () => {
    mockModels = [
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
        healthy: false,
        latency_p50_ms: 1214,
      },
      {
        id: "offline",
        label: "Offline",
        description: "",
        tier: "flash",
        plan_access: "free",
        available: false,
        input_price_per_m: 0,
        output_price_per_m: 0,
        quota_multiplier: 1,
        healthy: true,
        latency_p50_ms: 1214,
      },
    ];
    const { getByRole, getAllByText } = await render(<ModelsSettingsScreen />);
    expect(getAllByText("settings.model_degraded").length).toBe(2);
    expect(
      getByRole("button", { name: "Offline, settings.model_degraded" }).props
        .accessibilityState.disabled,
    ).toBe(true);
  });
});
