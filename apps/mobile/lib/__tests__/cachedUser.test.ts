import {
  cachedUserMatchesToken,
  clearCachedUser,
  mergeCachedUser,
  readCachedLocaleSync,
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

jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "/mock-cache/",
  getInfoAsync: jest.fn(),
  readAsStringAsync: jest.fn(),
  writeAsStringAsync: jest.fn(),
  deleteAsync: jest.fn(),
}));

/** The synchronous read the first frame uses (`lib/syncFileRead.ts`). */
const mockSyncFiles = new Map<string, string>();
jest.mock("expo-file-system", () => ({
  Paths: { document: "/mock-docs/", cache: "/mock-cache/" },
  File: class {
    private readonly path: string;
    constructor(directory: string, name: string) {
      this.path = `${directory}${name}`;
    }
    get exists() {
      return mockSyncFiles.has(this.path);
    }
    textSync() {
      return mockSyncFiles.get(this.path) ?? "";
    }
  },
}));

const user: User = {
  id: "u1",
  email: "a@b.com",
  name: "Alex",
  avatar_url: null,
  default_model: "smart-chat",
  plan: "free",
  enabled_models: null,
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

  it("reads the cached display fields and settings when present", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(
      JSON.stringify({
        v: 2,
        id: "u1",
        name: "Alex",
        avatar_url: null,
        plan: "pro",
        enabled_models: ["smart-chat"],
        memory_enabled: false,
        tts_voice: "verse",
      }),
    );
    await expect(readCachedUser()).resolves.toMatchObject({
      id: "u1",
      name: "Alex",
      avatar_url: null,
      plan: "pro",
      locale: "",
      enabled_models: ["smart-chat"],
      memory_enabled: false,
      tts_voice: "verse",
    });
  });

  it("does not paint a cache written before the settings were kept, and clears it", async () => {
    // An older build's file: this account's, or one another account's sign-out failed to delete.
    const v1 = JSON.stringify({ id: "u1", name: "Alex", avatar_url: null, plan: "free", locale: "fr" });
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(v1);
    await expect(readCachedUser()).resolves.toBeNull();
    await clearCachedUser();
    expect(deleteAsync).toHaveBeenCalledTimes(2);
    // Its language is not drawn in the first frame either.
    mockSyncFiles.set("/mock-cache/cached-user.json", v1);
    expect(readCachedLocaleSync()).toBeNull();
    mockSyncFiles.delete("/mock-cache/cached-user.json");
  });

  it("reads a setting of the wrong kind as unset, never as the bad value", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(
      JSON.stringify({ v: 2, id: "u1", plan: "gold", enabled_models: "smart-chat", memory_enabled: "yes", tts_voice: 3 }),
    );
    await expect(readCachedUser()).resolves.toMatchObject({
      plan: "free", enabled_models: null, memory_enabled: true, tts_voice: null,
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
      JSON.stringify({ v: 2, email: "a@b.com" }),
    );
    await expect(readCachedUser()).resolves.toBeNull();
  });

  it("writes the display fields and the settings the phone acts on", async () => {
    await writeCachedUser(user);
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "/mock-cache/cached-user.json",
      JSON.stringify({
        v: 2,
        id: "u1",
        name: "Alex",
        avatar_url: null,
        locale: "en",
        plan: "free",
        default_model: "smart-chat",
        enabled_models: null,
        memory_enabled: true,
        response_tone: "neutral",
      }),
    );
  });

  it("does NOT persist email, push or reminder switches, location, age, or custom_instructions", async () => {
    await writeCachedUser(user);
    const written = (writeAsStringAsync as jest.Mock).mock.calls[0][1] as string;
    const parsed = JSON.parse(written) as Record<string, unknown>;
    // PII and the switches the bootstrap sync acts on must be absent from the cached blob.
    expect(parsed).not.toHaveProperty("email");
    expect(parsed).not.toHaveProperty("push_notifications_enabled");
    expect(parsed).not.toHaveProperty("email_reminders_enabled");
    expect(parsed).not.toHaveProperty("reminder_lead_minutes");
    expect(parsed).not.toHaveProperty("location");
    expect(parsed).not.toHaveProperty("location_enabled");
    expect(parsed).not.toHaveProperty("age");
    expect(parsed).not.toHaveProperty("country");
    expect(parsed).not.toHaveProperty("job");
    expect(parsed).not.toHaveProperty("custom_instructions");
    expect(parsed).not.toHaveProperty("timezone");
  });

  it("keeps the language, so a cold start draws its first frame in it", async () => {
    await writeCachedUser({ ...user, locale: "es" });
    const written = (writeAsStringAsync as jest.Mock).mock.calls[0][1] as string;
    expect(JSON.parse(written)).toMatchObject({ locale: "es" });

    expect(readCachedLocaleSync()).toBeNull();
    mockSyncFiles.set("/mock-cache/cached-user.json", written);
    expect(readCachedLocaleSync()).toBe("es");
    mockSyncFiles.set("/mock-cache/cached-user.json", JSON.stringify({ id: "u1", plan: "free" }));
    expect(readCachedLocaleSync()).toBeNull();
    mockSyncFiles.set("/mock-cache/cached-user.json", "{half a file");
    expect(readCachedLocaleSync()).toBeNull();

    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(written);
    expect(mergeCachedUser((await readCachedUser())!).locale).toBe("es");
  });

  it("keeps the AI-consent time so a cold start does not ask again", async () => {
    await writeCachedUser({ ...user, ai_data_consent_at: "2026-10-19T12:00:00Z" });
    const written = (writeAsStringAsync as jest.Mock).mock.calls[0][1] as string;
    expect(JSON.parse(written)).toMatchObject({ ai_data_consent_at: "2026-10-19T12:00:00Z" });

    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(written);
    const cached = await readCachedUser();
    expect(cached?.ai_data_consent_at).toBe("2026-10-19T12:00:00Z");
    expect(mergeCachedUser(cached!).ai_data_consent_at).toBe("2026-10-19T12:00:00Z");
  });

  it("reads consent as unknown (undefined) from a cache written without the field", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(
      JSON.stringify({ v: 2, id: "u1", name: "Alex", avatar_url: null, plan: "free" }),
    );
    expect((await readCachedUser())?.ai_data_consent_at).toBeUndefined();

    (readAsStringAsync as jest.Mock).mockResolvedValue(
      JSON.stringify({ v: 2, id: "u1", name: null, avatar_url: null, plan: "free", ai_data_consent_at: null }),
    );
    expect((await readCachedUser())?.ai_data_consent_at).toBeNull();
  });

  it("clears the cached user", async () => {
    await clearCachedUser();
    expect(deleteAsync).toHaveBeenCalledWith("/mock-cache/cached-user.json", {
      idempotent: true,
    });
  });

  it("mergeCachedUser keeps the cached plan and settings and defaults the rest", async () => {
    await writeCachedUser({ ...user, plan: "pro", enabled_models: ["smart-chat"], tts_voice: "verse" });
    const written = (writeAsStringAsync as jest.Mock).mock.calls[0][1] as string;
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(written);
    const merged = mergeCachedUser((await readCachedUser())!);
    // Display fields and settings come from the cache.
    expect(merged.id).toBe("u1");
    expect(merged.name).toBe("Alex");
    expect(merged.plan).toBe("pro");
    expect(merged.enabled_models).toEqual(["smart-chat"]);
    expect(merged.memory_enabled).toBe(true);
    expect(merged.tts_voice).toBe("verse");
    // PII and switches are defaulted (empty/false/null) — replaced by api.me() on launch.
    expect(merged.email).toBe("");
    expect(merged.push_notifications_enabled).toBe(false);
    expect(merged.location).toBeNull();
    expect(merged.age).toBeNull();
    expect(merged.custom_instructions).toBeNull();
  });
});

it("finishes an already-started user cache write before clearing for signout", async () => {
  let finish!: () => void;
  let disk: string | null = null;
  (writeAsStringAsync as jest.Mock).mockImplementationOnce(async (_path, data) => {
    await new Promise<void>((resolve) => { finish = resolve; });
    disk = data;
  });
  (deleteAsync as jest.Mock).mockImplementationOnce(async () => { disk = null; });
  const write = writeCachedUser(user);
  await Promise.resolve();
  const clear = clearCachedUser();
  await Promise.resolve();
  finish();
  await Promise.all([write, clear]);
  expect(disk).toBeNull();
});

function accessTokenFor(sub: unknown): string {
  const encode = (value: unknown) => btoa(JSON.stringify(value)).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode({ sub })}.signature`;
}

it("selects cached display fields only for the stored token's subject", () => {
  expect(cachedUserMatchesToken(user, accessTokenFor(user.id))).toBe(true);
  expect(cachedUserMatchesToken(user, accessTokenFor("another-account"))).toBe(false);
});

it.each(["opaque-token", "a.@@.b", "a.bnVsbA.b", "a.e30.b", "a.e30.", accessTokenFor(123)])(
  "skips cached display fields for an unreadable or missing subject: %s", (token) => {
    expect(cachedUserMatchesToken(user, token)).toBe(false);
  },
);
