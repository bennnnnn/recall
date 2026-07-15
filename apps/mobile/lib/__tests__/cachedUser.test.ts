jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "/mock-cache/",
  getInfoAsync: jest.fn(),
  readAsStringAsync: jest.fn(),
  writeAsStringAsync: jest.fn(),
  deleteAsync: jest.fn(),
}));

import {
  clearCachedUser,
  mergeCachedUser,
  readCachedUser,
  writeCachedUser,
} from "@/lib/cachedUser";
import type { User } from "@/lib/api/types";
import {
  deleteAsync,
  getInfoAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";

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

  it("reads a cached user subset (id/name/avatar/plan only) when present", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(
      JSON.stringify({
        id: "u1",
        name: "Alex",
        avatar_url: null,
        plan: "free",
      }),
    );
    await expect(readCachedUser()).resolves.toEqual({
      id: "u1",
      name: "Alex",
      avatar_url: null,
      plan: "free",
    });
  });

  it("returns null for malformed cache content", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue("not json");
    await expect(readCachedUser()).resolves.toBeNull();
  });

  it("returns null when the parsed cache has no id", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(
      JSON.stringify({ email: "a@b.com" }),
    );
    await expect(readCachedUser()).resolves.toBeNull();
  });

  it("writes ONLY the non-sensitive display fields to disk (strips PII/prefs)", async () => {
    await writeCachedUser(user);
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "/mock-cache/cached-user.json",
      JSON.stringify({
        id: "u1",
        name: "Alex",
        avatar_url: null,
        plan: "free",
      }),
    );
  });

  it("does NOT persist email, prefs, location, age, or custom_instructions", async () => {
    await writeCachedUser(user);
    const written = (writeAsStringAsync as jest.Mock).mock.calls[0][1] as string;
    const parsed = JSON.parse(written) as Record<string, unknown>;
    // PII and prefs must be absent from the cached blob.
    expect(parsed).not.toHaveProperty("email");
    expect(parsed).not.toHaveProperty("push_notifications_enabled");
    expect(parsed).not.toHaveProperty("email_reminders_enabled");
    expect(parsed).not.toHaveProperty("reminder_lead_minutes");
    expect(parsed).not.toHaveProperty("memory_enabled");
    expect(parsed).not.toHaveProperty("location");
    expect(parsed).not.toHaveProperty("age");
    expect(parsed).not.toHaveProperty("country");
    expect(parsed).not.toHaveProperty("job");
    expect(parsed).not.toHaveProperty("custom_instructions");
    expect(parsed).not.toHaveProperty("default_model");
    expect(parsed).not.toHaveProperty("locale");
    expect(parsed).not.toHaveProperty("timezone");
  });

  it("clears the cached user", async () => {
    await clearCachedUser();
    expect(deleteAsync).toHaveBeenCalledWith("/mock-cache/cached-user.json", {
      idempotent: true,
    });
  });

  it("mergeCachedUser fills re-fetched fields with safe defaults", async () => {
    const merged = mergeCachedUser({
      id: "u1",
      name: "Alex",
      avatar_url: null,
      plan: "free",
    });
    // Display fields come from the cache.
    expect(merged.id).toBe("u1");
    expect(merged.name).toBe("Alex");
    expect(merged.plan).toBe("free");
    // PII/prefs are defaulted (empty/false/null) — replaced by api.me() on launch.
    expect(merged.email).toBe("");
    expect(merged.push_notifications_enabled).toBe(false);
    expect(merged.memory_enabled).toBe(false);
    expect(merged.location).toBeNull();
    expect(merged.age).toBeNull();
    expect(merged.custom_instructions).toBeNull();
  });
});
