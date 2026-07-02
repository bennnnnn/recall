import * as SecureStore from "expo-secure-store";

import {
  clearReminderLeadPrefs,
  getReminderLeadMinutes,
  setReminderLeadMinutes,
} from "@/lib/reminderPrefs";

jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

describe("reminderPrefs", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("clearReminderLeadPrefs deletes SecureStore key and resets cache", async () => {
    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue("15");
    await getReminderLeadMinutes();
    await clearReminderLeadPrefs();

    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith("reminder_lead_minutes");

    (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
    await expect(getReminderLeadMinutes()).resolves.toBe(10);
  });

  it("setReminderLeadMinutes persists chosen value", async () => {
    await setReminderLeadMinutes(30);
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith("reminder_lead_minutes", "30");
  });
});
