import * as FileSystem from "expo-file-system/legacy";
import * as SecureStore from "expo-secure-store";

import {
  clearReminderLeadPrefs,
  getReminderLeadMinutes,
  resetReminderLeadCache,
  setReminderLeadMinutes,
} from "@/lib/reminderPrefs";

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

  it("clearReminderLeadPrefs deletes the file and legacy Keychain key", async () => {
    getInfoAsync.mockResolvedValue({ exists: true });
    readAsStringAsync.mockResolvedValue("15");
    await getReminderLeadMinutes();
    await clearReminderLeadPrefs();

    expect(deleteAsync).toHaveBeenCalledWith("file:///docs/recall.reminder-lead-minutes.txt", {
      idempotent: true,
    });
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith("reminder_lead_minutes");

    getInfoAsync.mockResolvedValue({ exists: false });
    await expect(getReminderLeadMinutes()).resolves.toBe(10);
  });

  it("setReminderLeadMinutes persists to the filesystem, not Keychain", async () => {
    await setReminderLeadMinutes(30);
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "file:///docs/recall.reminder-lead-minutes.txt",
      "30",
    );
    expect(SecureStore.setItemAsync).not.toHaveBeenCalled();
  });

  it("migrates a legacy Keychain lead time onto the filesystem", async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue("15");
    await expect(getReminderLeadMinutes()).resolves.toBe(15);
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "file:///docs/recall.reminder-lead-minutes.txt",
      "15",
    );
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
  const write = setReminderLeadMinutes(30);
  await Promise.resolve();
  const clear = clearReminderLeadPrefs();
  await Promise.resolve();
  finish();
  await Promise.all([write, clear]);
  expect(disk).toBeNull();
});
