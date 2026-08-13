import * as FileSystem from "expo-file-system/legacy";
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

jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "file:///docs/",
  getInfoAsync: jest.fn(),
  readAsStringAsync: jest.fn(),
  writeAsStringAsync: jest.fn(),
}));

const getInfoAsync = FileSystem.getInfoAsync as jest.Mock;
const readAsStringAsync = FileSystem.readAsStringAsync as jest.Mock;
const writeAsStringAsync = FileSystem.writeAsStringAsync as jest.Mock;

describe("appearancePrefs", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetAppearanceRuntime();
    resetAppearancePreferenceCache();
    getInfoAsync.mockResolvedValue({ exists: false });
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
  });

  it("defaults to system when unset", async () => {
    await expect(getAppearancePreference()).resolves.toBe("system");
  });

  it("persists manual preference to the filesystem, not Keychain", async () => {
    await setAppearancePreference("dark");
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "file:///docs/recall.appearance-preference.txt",
      "dark",
    );
    expect(SecureStore.setItemAsync).not.toHaveBeenCalled();
  });

  it("reads the filesystem value when present", async () => {
    getInfoAsync.mockResolvedValue({ exists: true });
    readAsStringAsync.mockResolvedValue("light");
    await expect(getAppearancePreference()).resolves.toBe("light");
    expect(SecureStore.getItemAsync).not.toHaveBeenCalled();
  });

  it("migrates a legacy Keychain preference onto the filesystem", async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue("dark");
    await expect(getAppearancePreference()).resolves.toBe("dark");
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "file:///docs/recall.appearance-preference.txt",
      "dark",
    );
  });
});
