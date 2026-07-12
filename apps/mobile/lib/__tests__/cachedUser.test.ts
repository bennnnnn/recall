jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "/mock-cache/",
  getInfoAsync: jest.fn(),
  readAsStringAsync: jest.fn(),
  writeAsStringAsync: jest.fn(),
  deleteAsync: jest.fn(),
}));

import { clearCachedUser, readCachedUser, writeCachedUser } from "@/lib/cachedUser";
import type { User } from "@/lib/api/types";
import { deleteAsync, getInfoAsync, readAsStringAsync, writeAsStringAsync } from "expo-file-system/legacy";

const user: User = {
  id: "u1",
  email: "a@b.com",
  name: "Alex",
  avatar_url: null,
  default_model: "smart-chat",
  plan: "free",
  enabled_models: null,
  response_style: "balanced",
  response_tone: "neutral",
  memory_enabled: true,
  push_notifications_enabled: true,
  email_reminders_enabled: false,
  reminder_lead_minutes: 10,
  locale: "en",
  timezone: "UTC",
  location: null,
  location_enabled: false,
  custom_instructions: null,
  age: null,
  country: null,
  job: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("cachedUser", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns null when no cache file exists", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: false });
    await expect(readCachedUser()).resolves.toBeNull();
  });

  it("reads a cached user when present", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(JSON.stringify(user));
    await expect(readCachedUser()).resolves.toEqual(user);
  });

  it("returns null for malformed cache content", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue("not json");
    await expect(readCachedUser()).resolves.toBeNull();
  });

  it("returns null when the parsed cache has no id", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(JSON.stringify({ email: "a@b.com" }));
    await expect(readCachedUser()).resolves.toBeNull();
  });

  it("writes the user to disk", async () => {
    await writeCachedUser(user);
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "/mock-cache/cached-user.json",
      JSON.stringify(user),
    );
  });

  it("clears the cached user", async () => {
    await clearCachedUser();
    expect(deleteAsync).toHaveBeenCalledWith("/mock-cache/cached-user.json", {
      idempotent: true,
    });
  });
});
