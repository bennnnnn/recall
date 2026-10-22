import * as FileSystem from "expo-file-system/legacy";
import * as SecureStore from "expo-secure-store";

import {
  getAppearancePreference,
  readAppearancePreferenceSync,
  resetAppearancePreferenceCache,
  setAppearancePreference,
} from "@/lib/appearancePrefs";
import { resetAppearanceRuntime } from "@/lib/appearanceRuntime";

/** The synchronous file system the first frame reads (`lib/syncFileRead.ts`). */
const mockSyncFiles = new Map<string, string>();
jest.mock("expo-file-system", () => ({
  Paths: { document: "file:///docs/", cache: "file:///cache/" },
  File: class {
    private readonly path: string;
    constructor(directory: string, name: string) {
      this.path = `${directory}${name}`;
    }
    get exists() {
      return mockSyncFiles.has(this.path);
    }
    textSync() {
      return mockSyncFiles.get(this.path) ?? "";
    }
  },
}));

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
  deleteAsync: jest.fn(),
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
    mockSyncFiles.clear();
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

  it("writes the file for an unset preference too, so the Keychain is read once", async () => {
    await expect(getAppearancePreference()).resolves.toBe("system");
    expect(SecureStore.getItemAsync).toHaveBeenCalledTimes(1);
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "file:///docs/recall.appearance-preference.txt",
      "system",
    );
  });

  it("keeps a choice made while the old value moves out of the Keychain", async () => {
    let answer!: (value: string | null) => void;
    (SecureStore.getItemAsync as jest.Mock).mockReturnValue(new Promise((resolve) => { answer = resolve; }));
    const moving = getAppearancePreference();
    await setAppearancePreference("light");
    answer("dark");
    await expect(moving).resolves.toBe("light");
    expect(writeAsStringAsync).toHaveBeenLastCalledWith(
      "file:///docs/recall.appearance-preference.txt",
      "light",
    );
  });

  it("reads the saved preference synchronously for the first frame", async () => {
    expect(readAppearancePreferenceSync()).toBeNull();
    mockSyncFiles.set("file:///docs/recall.appearance-preference.txt", "dark");
    expect(readAppearancePreferenceSync()).toBe("dark");
    // The asynchronous reader then answers from memory.
    await expect(getAppearancePreference()).resolves.toBe("dark");
    expect(getInfoAsync).not.toHaveBeenCalled();
  });
});
