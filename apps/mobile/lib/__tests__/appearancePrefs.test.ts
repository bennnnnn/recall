import * as SecureStore from "expo-secure-store";

import {
  getAppearancePreference,
  resetAppearancePreferenceCache,
  setAppearancePreference,
} from "@/lib/appearancePrefs";
import { resetAppearanceRuntime } from "@/lib/appearanceRuntime";

jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

describe("appearancePrefs", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetAppearanceRuntime();
    resetAppearancePreferenceCache();
  });

  it("defaults to system when unset", async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
    await expect(getAppearancePreference()).resolves.toBe("system");
  });

  it("persists manual preference", async () => {
    await setAppearancePreference("dark");
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith("appearance_preference", "dark");
  });
});
