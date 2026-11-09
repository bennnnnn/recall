/**
 * createFilePref: the one cache, read and write around a device preference's file. Six
 * preferences each wrote this by hand, and all but onboarding let a read that landed after a
 * tap in Settings put the old value back for the session.
 */
import * as FileSystem from "expo-file-system/legacy";

import { getAccentPreference, resetAccentPreferenceCache, setAccentPreference } from "@/lib/accentPrefs";
import { createFilePref } from "@/lib/filePrefs";

/** The phone's files, as the legacy file system reads and writes them. */
const mockFiles = new Map<string, string>();
jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "file:///docs/",
  getInfoAsync: jest.fn(async (path: string) => ({ exists: mockFiles.has(path) })),
  readAsStringAsync: jest.fn(async (path: string) => mockFiles.get(path) ?? ""),
  writeAsStringAsync: jest.fn(async (path: string, value: string) => {
    mockFiles.set(path, value);
  }),
  deleteAsync: jest.fn(),
}));

const readAsStringAsync = FileSystem.readAsStringAsync as jest.Mock;
const writeAsStringAsync = FileSystem.writeAsStringAsync as jest.Mock;

const parseLayout = (raw: string | null) => (raw === "column" ? "column" : "grid");

beforeEach(() => {
  mockFiles.clear();
  jest.clearAllMocks();
  resetAccentPreferenceCache();
});

describe("createFilePref", () => {
  it("reads the file once, and gives the default with no file", async () => {
    const pref = createFilePref("recall.demo.txt", parseLayout);
    expect(pref.peek()).toBeNull();
    await expect(pref.get()).resolves.toBe("grid");
    mockFiles.set("file:///docs/recall.demo.txt", "column");
    await expect(pref.get()).resolves.toBe("grid");
    expect(readAsStringAsync).not.toHaveBeenCalled();
  });

  it("keeps a value set while the file was being read", async () => {
    mockFiles.set("file:///docs/recall.accent-preference.txt", "ocean");
    let finishRead!: (value: string) => void;
    readAsStringAsync.mockImplementationOnce(() => new Promise((resolve) => {
      finishRead = resolve;
    }));
    const reading = getAccentPreference();
    await Promise.resolve();
    await setAccentPreference("violet");
    finishRead("ocean");
    await expect(reading).resolves.toBe("violet");
    await expect(getAccentPreference()).resolves.toBe("violet");
    expect(mockFiles.get("file:///docs/recall.accent-preference.txt")).toBe("violet");
  });

  it("writes in turn, so the file ends as the last value set", async () => {
    const pref = createFilePref("recall.demo.txt", parseLayout);
    let finishFirst!: () => void;
    writeAsStringAsync.mockImplementationOnce(async (path: string, value: string) => {
      await new Promise<void>((resolve) => { finishFirst = resolve; });
      mockFiles.set(path, value);
    });
    const first = pref.set("column");
    await Promise.resolve();
    const second = pref.set("grid");
    const third = pref.set("column");
    finishFirst();
    await Promise.all([first, second, third]);
    expect(mockFiles.get("file:///docs/recall.demo.txt")).toBe("column");
    // The middle value never reached the disk: the last one replaced it while it waited.
    expect(writeAsStringAsync.mock.calls.map((call) => call[1])).toEqual(["column", "column"]);
    expect(pref.peek()).toBe("column");
  });

  it("writes the value as `serialize` spells it", async () => {
    const pref = createFilePref("recall.flag.txt", (raw) => raw === "on", (on) => (on ? "on" : "off"));
    await pref.set(false);
    expect(mockFiles.get("file:///docs/recall.flag.txt")).toBe("off");
    pref.reset();
    await expect(pref.get()).resolves.toBe(false);
  });
});
