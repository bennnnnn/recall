import React, { useLayoutEffect } from "react";
import { AppState, Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { SETTINGS_PROFILE_STALE_MS, useRereadProfile, type RereadProfile } from "@/contexts/profileReread";
import { api, setTokenRefreshHandler, type User } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { readCachedUser, writeCachedUser } from "@/lib/cachedUser";
import { trackZoneReport } from "@/lib/zoneReport";

jest.mock("@/lib/api", () => ({
  api: { me: jest.fn(), updateMe: jest.fn() },
  loginWithGoogle: jest.fn(), loginWithApple: jest.fn(), loginWithDev: jest.fn(),
  logoutSession: jest.fn(), setTokenRefreshHandler: jest.fn(), setUnauthorizedHandler: jest.fn(),
  setConsentRequiredHandler: jest.fn(),
}));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => 0,
  invalidateSession: () => 1,
  getToken: jest.fn(), getRefreshToken: jest.fn(async () => "refresh-a"),
  setTokenPair: jest.fn(async () => true),
  clearToken: jest.fn(async () => undefined),
  getOnboarded: jest.fn(async () => true), setOnboarded: jest.fn(), clearOnboarded: jest.fn(),
  CorruptSessionError: class CorruptSessionError extends Error {},
}));
jest.mock("@/lib/cachedUser", () => ({
  cachedUserMatchesToken: jest.fn(() => true),
  readCachedUser: jest.fn(), writeCachedUser: jest.fn(), clearCachedUser: jest.fn(),
  mergeCachedUser: (value: User) => value,
}));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({ bg: "white", primary: "blue" }) }));
jest.mock("@/lib/i18n", () => ({ ensureLocale: jest.fn() }));
jest.mock("@/hooks/useBootstrapSync", () => ({ useBootstrapSync: jest.fn() }));
jest.mock("@/lib/apple-auth", () => ({ signInWithAppleCredentials: jest.fn() }));
jest.mock("@/lib/google-auth", () => ({ signInWithGoogleIdToken: jest.fn(), signOutGoogle: jest.fn() }));
jest.mock("@/lib/signOutCleanup", () => ({ clearSignedOutAccount: jest.fn() }));
jest.mock("@/lib/sentry", () => ({ reportCorruptSessionCleared: jest.fn() }));
jest.mock("@/lib/syncRecords", () => ({ forgetSyncRecords: jest.fn(async () => undefined) }));
jest.mock("@/lib/images/imageCaches", () => ({ clearImageCaches: jest.fn(async () => undefined) }));
jest.mock("@/lib/pendingLogout", () => ({ endServerSession: jest.fn(async () => undefined), watchPendingLogouts: jest.fn(() => () => {}) }));

const userA = { id: "account-a", name: "Alice", locale: "en", tts_voice: "alloy" } as unknown as User;
/** The same account after another device picked a voice. */
const elsewhere = { ...userA, tts_voice: "verse" } as User;

let auth: ReturnType<typeof useAuth>;
let reread: RereadProfile;
const rendered = jest.fn();

function Probe() {
  const value = useAuth();
  const read = useRereadProfile();
  rendered();
  useLayoutEffect(() => { auth = value; reread = read; }, [value, read]);
  return <Text>{value.user?.name ?? "signed-out"}</Text>;
}

const appStateListeners = new Set<(state: string) => void>();
let now = 1_000_000;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

async function mount() {
  await render(<AuthProvider><Probe /></AuthProvider>);
  (api.me as jest.Mock).mockClear();
}

async function returnToForeground(afterMs: number) {
  await act(async () => { for (const listener of [...appStateListeners]) listener("background"); });
  now += afterMs;
  await act(async () => { for (const listener of [...appStateListeners]) listener("active"); });
}

async function flush() {
  await act(async () => { await new Promise<void>((resolve) => { setImmediate(() => resolve()); }); });
}

beforeEach(() => {
  jest.clearAllMocks();
  appStateListeners.clear();
  now = 1_000_000;
  jest.spyOn(Date, "now").mockImplementation(() => now);
  jest.spyOn(AppState, "addEventListener").mockImplementation(((_type: string, listener: (state: string) => void) => {
    appStateListeners.add(listener);
    return { remove: () => appStateListeners.delete(listener) };
  }) as typeof AppState.addEventListener);
  (getToken as jest.Mock).mockResolvedValue("access-a");
  (readCachedUser as jest.Mock).mockResolvedValue(userA);
  (api.me as jest.Mock).mockResolvedValue(userA);
});

afterEach(() => {
  jest.restoreAllMocks();
});

it("reads the user again on a return to the foreground, so a change made elsewhere shows", async () => {
  await mount();
  (api.me as jest.Mock).mockResolvedValue(elsewhere);
  await returnToForeground(60_000);
  await flush();
  expect(api.me).toHaveBeenCalledTimes(1);
  expect(api.me).toHaveBeenCalledWith("access-a");
  expect((auth.user as unknown as { tts_voice: string }).tts_voice).toBe("verse");
  expect(writeCachedUser).toHaveBeenLastCalledWith(elsewhere);
});

it("reads nothing on a return within 30 s of the last read", async () => {
  await mount();
  await returnToForeground(10_000);
  await flush();
  expect(api.me).not.toHaveBeenCalled();
});

it("a Settings page that gains focus reads once, and page hops within 30 s read nothing", async () => {
  await mount();
  now += SETTINGS_PROFILE_STALE_MS;
  (api.me as jest.Mock).mockResolvedValue(elsewhere);
  await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); reread(SETTINGS_PROFILE_STALE_MS); });
  await flush();
  expect(api.me).toHaveBeenCalledTimes(1);
  now += SETTINGS_PROFILE_STALE_MS - 1;
  await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); });
  await flush();
  expect(api.me).toHaveBeenCalledTimes(1);
  now += 1;
  await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); });
  await flush();
  expect(api.me).toHaveBeenCalledTimes(2);
});

it("a save's answer counts as a read", async () => {
  await mount();
  now += 60_000;
  (api.updateMe as jest.Mock).mockResolvedValue({ ...userA, name: "Ann" });
  await act(async () => { await auth.updateUser({ name: "Ann" }); });
  now += 10_000;
  await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); });
  await flush();
  expect(api.me).not.toHaveBeenCalled();
});

it("an unchanged answer keeps the user as it is: no re-render, no cache write", async () => {
  await mount();
  const shown = auth.user;
  (writeCachedUser as jest.Mock).mockClear();
  const before = rendered.mock.calls.length;
  now += 60_000;
  (api.me as jest.Mock).mockResolvedValue({ ...userA });
  await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); });
  await flush();
  expect(api.me).toHaveBeenCalledTimes(1);
  expect(auth.user).toBe(shown);
  expect(rendered).toHaveBeenCalledTimes(before);
  expect(writeCachedUser).not.toHaveBeenCalled();
});

it("a token rotation reads nothing; the next read sends the new token", async () => {
  await mount();
  const onRefresh = (setTokenRefreshHandler as jest.Mock).mock.calls.at(-1)[0];
  now += 60_000;
  await act(async () => { onRefresh("access-rotated", null); });
  await flush();
  expect(api.me).not.toHaveBeenCalled();
  await returnToForeground(1_000);
  await flush();
  expect(api.me).toHaveBeenCalledWith("access-rotated");
});

it("does not read while a save waits: the save's answer is the newer read", async () => {
  await mount();
  const save = deferred<User>();
  (api.updateMe as jest.Mock).mockReturnValue(save.promise);
  let pending!: Promise<void>;
  await act(async () => { pending = auth.updateUser({ tts_voice: "ash" } as Partial<User>); });
  now += 60_000;
  await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); });
  await flush();
  expect(api.me).not.toHaveBeenCalled();
  await act(async () => { save.resolve({ ...userA, tts_voice: "ash" } as User); await pending; });
  expect((auth.user as unknown as { tts_voice: string }).tts_voice).toBe("ash");
});

it("keeps a save made while a read was in flight, whichever answers last", async () => {
  await mount();
  now += 60_000;
  const read = deferred<User>();
  (api.me as jest.Mock).mockReturnValue(read.promise);
  await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); });
  await flush();
  expect(api.me).toHaveBeenCalledTimes(1);
  const saved = { ...userA, tts_voice: "ash" } as User;
  (api.updateMe as jest.Mock).mockResolvedValue(saved);
  await act(async () => { await auth.updateUser({ tts_voice: "ash" } as Partial<User>); });
  // The read the server answered before the save: the old voice.
  await act(async () => { read.resolve(userA); });
  await flush();
  expect((auth.user as unknown as { tts_voice: string }).tts_voice).toBe("ash");
  expect(writeCachedUser).toHaveBeenLastCalledWith(saved);
});

it("drops a read that lands after a local merge", async () => {
  await mount();
  now += 60_000;
  const read = deferred<User>();
  (api.me as jest.Mock).mockReturnValue(read.promise);
  await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); });
  await flush();
  await act(async () => { auth.mergeUser({ name: "Merged" }); });
  await act(async () => { read.resolve(elsewhere); });
  await flush();
  expect(auth.user?.name).toBe("Merged");
  expect((auth.user as unknown as { tts_voice: string }).tts_voice).toBe("alloy");
});

it("waits for the zone report in flight, so the read never carries the old zone", async () => {
  await mount();
  const report = deferred<void>();
  trackZoneReport(report.promise);
  now += 60_000;
  await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); });
  await flush();
  expect(api.me).not.toHaveBeenCalled();
  await act(async () => { report.resolve(); });
  await flush();
  expect(api.me).toHaveBeenCalledTimes(1);
});

it("a read that fails (offline) is not tried again on the next page hop", async () => {
  await mount();
  now += 60_000;
  (api.me as jest.Mock).mockRejectedValue(new Error("offline"));
  await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); });
  await flush();
  now += 5_000;
  await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); });
  await flush();
  expect(api.me).toHaveBeenCalledTimes(1);
  expect(auth.user?.id).toBe(userA.id);
});

describe("back after an outage", () => {
  // The connection check's reports (lib/reconnectRefresh.ts), with its 0-10 s spread made 0.
  const { reportDisconnected, reportReconnected } =
    jest.requireActual<typeof import("@/lib/reconnectRefresh")>("@/lib/reconnectRefresh");

  async function reconnect() {
    await act(async () => { reportReconnected(); });
    await act(async () => { await new Promise<void>((resolve) => { setTimeout(resolve, 5); }); });
    await flush();
  }

  beforeEach(() => {
    jest.spyOn(Math, "random").mockReturnValue(0);
  });

  it("an offline launch confirms the cached profile once the API answers again", async () => {
    (api.me as jest.Mock).mockRejectedValueOnce(new Error("offline"));
    await mount();
    expect(auth.user?.id).toBe(userA.id);
    expect(auth.profileValidated).toBe(false);
    await act(async () => { reportDisconnected(); });
    now += 5_000;
    (api.me as jest.Mock).mockResolvedValue(elsewhere);
    await reconnect();
    expect(api.me).toHaveBeenCalledTimes(1);
    expect(auth.profileValidated).toBe(true);
    expect((auth.user as unknown as { tts_voice: string }).tts_voice).toBe("verse");
  });

  it("reads nothing again for a profile the server confirmed this run", async () => {
    await mount();
    await act(async () => { reportDisconnected(); });
    now += 60_000;
    await reconnect();
    expect(api.me).not.toHaveBeenCalled();
  });

  it("a try that failed during the outage does not hold back the read once it ends", async () => {
    (api.me as jest.Mock).mockRejectedValueOnce(new Error("offline"));
    await mount();
    await act(async () => { reportDisconnected(); });
    (api.me as jest.Mock).mockRejectedValueOnce(new Error("offline"));
    await act(async () => { reread(SETTINGS_PROFILE_STALE_MS); });
    await flush();
    now += 2_000;
    (api.me as jest.Mock).mockResolvedValue(userA);
    await reconnect();
    expect(api.me).toHaveBeenCalledTimes(2);
    expect(auth.profileValidated).toBe(true);
  });
});
