import { deleteAsync, getInfoAsync, readAsStringAsync, writeAsStringAsync } from "expo-file-system/legacy";

import { forgetSyncRecords, recentSyncAt, recordSync } from "@/lib/syncRecords";

const mockFiles = new Map<string, string>();
jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "file:///docs/",
  getInfoAsync: jest.fn(async (path: string) => ({ exists: mockFiles.has(path) })),
  readAsStringAsync: jest.fn(async (path: string) => mockFiles.get(path) ?? ""),
  writeAsStringAsync: jest.fn(async (path: string, value: string) => {
    mockFiles.set(path, value);
  }),
  deleteAsync: jest.fn(async (path: string) => {
    mockFiles.delete(path);
  }),
}));
jest.mock("expo-secure-store", () => ({ getItemAsync: jest.fn(), deleteItemAsync: jest.fn() }));

const HOUR = 60 * 60_000;

beforeEach(() => {
  mockFiles.clear();
  jest.clearAllMocks();
});

describe("sync records", () => {
  it("answers for the same account and variant inside the window only", async () => {
    await recordSync("push", "user-1", "on", 1_000);
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "file:///docs/recall.synced-push.json",
      JSON.stringify({ account: "user-1", variant: "on", at: 1_000 }),
    );
    expect(await recentSyncAt("push", "user-1", 12 * HOUR, "on", 1_000 + HOUR)).toBe(1_000);
    expect(await recentSyncAt("push", "user-2", 12 * HOUR, "on", 1_000 + HOUR)).toBeNull();
    expect(await recentSyncAt("push", "user-1", 12 * HOUR, "off", 1_000 + HOUR)).toBeNull();
    expect(await recentSyncAt("push", "user-1", 12 * HOUR, "on", 1_000 + 13 * HOUR)).toBeNull();
    expect(await recentSyncAt("location", "user-1", 24 * HOUR, "", 1_000 + HOUR)).toBeNull();
  });

  it("does not trust a time from a clock that was set back, or a broken file", async () => {
    await recordSync("location", "user-1", "", 10 * HOUR);
    expect(await recentSyncAt("location", "user-1", 24 * HOUR, "", 9 * HOUR)).toBeNull();
    mockFiles.set("file:///docs/recall.synced-location.json", "{not json");
    expect(await recentSyncAt("location", "user-1", 24 * HOUR, "", 10 * HOUR)).toBeNull();
    expect(readAsStringAsync).toHaveBeenCalled();
    expect(getInfoAsync).toHaveBeenCalled();
  });

  it("forgets every record at sign-out", async () => {
    await recordSync("push", "user-1", "on");
    await recordSync("location", "user-1");
    await forgetSyncRecords();
    expect(mockFiles.size).toBe(0);
    expect(deleteAsync).toHaveBeenCalledTimes(2);
  });
});
