import Constants, { ExecutionEnvironment } from "expo-constants";

import { canUseDeviceLocation, canUseVoiceInput, isExpoGo } from "@/lib/expoRuntime";

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: {
    executionEnvironment: "storeClient",
    appOwnership: "expo",
    expoGoConfig: {},
  },
  ExecutionEnvironment: {
    Bare: "bare",
    Standalone: "standalone",
    StoreClient: "storeClient",
  },
}));

describe("expoRuntime", () => {
  it("exports location guard helpers", () => {
    expect(typeof isExpoGo).toBe("function");
    expect(typeof canUseDeviceLocation).toBe("function");
    expect(typeof canUseVoiceInput).toBe("function");
  });

  it("detects Expo Go", () => {
    (Constants as { executionEnvironment: string }).executionEnvironment =
      ExecutionEnvironment.StoreClient;
    (Constants as { appOwnership: string | null }).appOwnership = "expo";
    expect(isExpoGo()).toBe(true);
    expect(canUseDeviceLocation()).toBe(false);
    expect(canUseVoiceInput()).toBe(false);
  });

  it("does not treat bare dev builds as Expo Go even when expoGoConfig is set", () => {
    (Constants as { executionEnvironment: string }).executionEnvironment =
      ExecutionEnvironment.Bare;
    (Constants as { appOwnership: string | null }).appOwnership = null;
    expect(isExpoGo()).toBe(false);
    expect(canUseDeviceLocation()).toBe(true);
    expect(canUseVoiceInput()).toBe(true);
  });

  it("does not treat standalone builds as Expo Go", () => {
    (Constants as { executionEnvironment: string }).executionEnvironment =
      ExecutionEnvironment.Standalone;
    (Constants as { appOwnership: string | null }).appOwnership = null;
    expect(isExpoGo()).toBe(false);
  });
});
