import * as FileSystem from "expo-file-system/legacy";
import * as SecureStore from "expo-secure-store";

import {
  clearReminderLeadPrefs,
  getReminderLeadMinutes,
  resetReminderLeadCache,
  syncReminderLeadFromServer,
} from "@/features/todos/model/reminderPrefs";

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
const deleteAsync = FileSystem.deleteAsync as jest.Mock;

describe("reminderPrefs", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetReminderLeadCache();
    getInfoAsync.mockResolvedValue({ exists: false });
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
  });

  it("clearReminderLeadPrefs deletes the file", async () => {
    getInfoAsync.mockResolvedValue({ exists: true });
    readAsStringAsync.mockResolvedValue("15");
    await getReminderLeadMinutes();
    await clearReminderLeadPrefs();

    expect(deleteAsync).toHaveBeenCalledWith("file:///docs/recall.reminder-lead-minutes.txt", {
      idempotent: true,
    });

    getInfoAsync.mockResolvedValue({ exists: false });
    await expect(getReminderLeadMinutes()).resolves.toBe(10);
  });

  it("syncReminderLeadFromServer persists to the filesystem, not Keychain", async () => {
    await expect(syncReminderLeadFromServer(30)).resolves.toBe(30);
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "file:///docs/recall.reminder-lead-minutes.txt",
      "30",
    );
    expect(SecureStore.setItemAsync).not.toHaveBeenCalled();
  });

  it("reads the default, not the Keychain, when no file exists (DEAD-07)", async () => {
    await expect(getReminderLeadMinutes()).resolves.toBe(10);
    expect(SecureStore.getItemAsync).not.toHaveBeenCalled();
  });
});

it("does not restore a previous account's reminder preference after signout", async () => {
  let finish!: () => void;
  let disk: string | null = null;
  writeAsStringAsync.mockImplementationOnce(async (_path, value) => {
    await new Promise<void>((resolve) => { finish = resolve; });
    disk = value;
  });
  deleteAsync.mockImplementationOnce(async () => { disk = null; });
  const write = syncReminderLeadFromServer(30);
  await Promise.resolve();
  const clear = clearReminderLeadPrefs();
  await Promise.resolve();
  finish();
  await Promise.all([write, clear]);
  expect(disk).toBeNull();
});
