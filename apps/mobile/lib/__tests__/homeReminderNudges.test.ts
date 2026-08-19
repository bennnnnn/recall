import * as FileSystem from "expo-file-system/legacy";

import type { HomeUrgentTodo } from "@/lib/api";
import {
  filterHomeNudgeTodos,
  loadHomeNudgeState,
  pruneHomeNudgeState,
  saveHomeNudgeState,
} from "@/lib/homeReminderNudges";

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

function urgent(
  id: string,
  minutesUntil: number,
): HomeUrgentTodo {
  return {
    id,
    content: id,
    topic: "General",
    due_at: "2026-06-27T12:00:00.000Z",
    minutes_until: minutesUntil,
  };
}

describe("homeReminderNudges", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getInfoAsync.mockResolvedValue({ exists: false });
  });

  it("loads empty state when no file exists", async () => {
    const state = await loadHomeNudgeState("user-1");
    expect(state.dismissed.size).toBe(0);
    expect(state.overduePresented.size).toBe(0);
  });

  it("persists dismissed and overduePresented", async () => {
    await saveHomeNudgeState("user-1", {
      dismissed: new Set(["a"]),
      overduePresented: new Set(["b"]),
    });
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "file:///docs/recall.home-nudges.user-1.json",
      JSON.stringify({ dismissed: ["a"], overduePresented: ["b"] }),
    );
  });

  it("reads stored state from the filesystem", async () => {
    getInfoAsync.mockResolvedValue({ exists: true });
    readAsStringAsync.mockResolvedValue(
      JSON.stringify({ dismissed: ["a"], overduePresented: ["b"] }),
    );
    const state = await loadHomeNudgeState("user-1");
    expect(state.dismissed).toEqual(new Set(["a"]));
    expect(state.overduePresented).toEqual(new Set(["b"]));
  });

  it("prunes ids for todos that are gone or completed", () => {
    const pruned = pruneHomeNudgeState(
      {
        dismissed: new Set(["open", "done"]),
        overduePresented: new Set(["open", "gone"]),
      },
      ["open"],
    );
    expect(pruned.dismissed).toEqual(new Set(["open"]));
    expect(pruned.overduePresented).toEqual(new Set(["open"]));
  });
});

describe("filterHomeNudgeTodos", () => {
  const dueSoon = urgent("soon", 8);
  const overdue = urgent("late", -60);

  it("shows approaching and overdue when nothing was dismissed", () => {
    expect(
      filterHomeNudgeTodos(
        [dueSoon, overdue],
        { dismissed: new Set(), overduePresented: new Set() },
        new Set(),
      ).map((t) => t.id),
    ).toEqual(["soon", "late"]);
  });

  it("never shows a dismissed reminder, even if overdue", () => {
    expect(
      filterHomeNudgeTodos(
        [dueSoon, overdue],
        { dismissed: new Set(["soon", "late"]), overduePresented: new Set() },
        new Set(),
      ),
    ).toEqual([]);
  });

  it("hides overdue that was already presented in a previous session", () => {
    expect(
      filterHomeNudgeTodos(
        [overdue],
        { dismissed: new Set(), overduePresented: new Set(["late"]) },
        new Set(),
      ),
    ).toEqual([]);
  });

  it("keeps overdue visible in the same session after it is recorded as presented", () => {
    expect(
      filterHomeNudgeTodos(
        [overdue],
        { dismissed: new Set(), overduePresented: new Set(["late"]) },
        new Set(["late"]),
      ).map((t) => t.id),
    ).toEqual(["late"]);
  });

  it("still shows due-soon after a different reminder was presented as overdue", () => {
    expect(
      filterHomeNudgeTodos(
        [dueSoon],
        { dismissed: new Set(), overduePresented: new Set(["late"]) },
        new Set(),
      ).map((t) => t.id),
    ).toEqual(["soon"]);
  });
});
