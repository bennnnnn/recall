import * as FileSystem from "expo-file-system/legacy";

import {
  loadHomeNudgeState,
  pruneHomeNudgeState,
  saveHomeNudgeState,
} from "@/features/todos/model/homeReminderNudges";

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

describe("homeReminderNudges", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getInfoAsync.mockResolvedValue({ exists: false });
  });

  it("loads empty state when no file exists", async () => {
    const state = await loadHomeNudgeState("user-1");
    expect(state.dismissed.size).toBe(0);
  });

  it("persists dismissed ids", async () => {
    await saveHomeNudgeState("user-1", {
      dismissed: new Set(["a"]),
    });
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "file:///docs/recall.home-nudges.user-1.json",
      JSON.stringify({ dismissed: ["a"] }),
    );
  });

  it("reads stored dismissed ids from the filesystem", async () => {
    getInfoAsync.mockResolvedValue({ exists: true });
    readAsStringAsync.mockResolvedValue(
      JSON.stringify({ dismissed: ["a"], overduePresented: ["b"] }),
    );
    const state = await loadHomeNudgeState("user-1");
    expect(state.dismissed).toEqual(new Set(["a"]));
  });

  it("prunes ids for todos that are gone or completed", () => {
    const pruned = pruneHomeNudgeState(
      {
        dismissed: new Set(["open", "done"]),
      },
      ["open"],
    );
    expect(pruned.dismissed).toEqual(new Set(["open"]));
  });
});
