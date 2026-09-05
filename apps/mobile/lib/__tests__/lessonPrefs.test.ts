import * as FileSystem from "expo-file-system/legacy";

import {
  getLessonPrefs,
  parseLessonPrefs,
  resetLessonPrefsCache,
  setLessonPrefs,
} from "@/lib/lessonPrefs";

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

describe("lessonPrefs", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetLessonPrefsCache();
    getInfoAsync.mockResolvedValue({ exists: false });
  });

  it("defaults to effects on, no auto-read, and medium type", () => {
    expect(parseLessonPrefs(null)).toEqual({
      effectSound: true,
      readWords: false,
      fontSize: "medium",
    });
  });

  it("persists prefs to the filesystem, not Keychain", async () => {
    await setLessonPrefs({ effectSound: false, readWords: true, fontSize: "large" });
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "file:///docs/recall.lesson-prefs.json",
      JSON.stringify({ effectSound: false, readWords: true, fontSize: "large" }),
    );
  });

  it("reads a saved file", async () => {
    getInfoAsync.mockResolvedValue({ exists: true });
    readAsStringAsync.mockResolvedValue(
      JSON.stringify({ effectSound: false, readWords: true, fontSize: "small" }),
    );
    await expect(getLessonPrefs()).resolves.toEqual({
      effectSound: false,
      readWords: true,
      fontSize: "small",
    });
  });
});
