/**
 * The secure store keeps every item on this phone, and a launch tells an upgrade from a
 * reinstall (`lib/secureStore.ts`):
 *
 * - every read, write and delete passes AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY, so a backup or
 *   Quick Start never carries the sign-in or the installation id to another phone;
 * - an upgrade (no marker, this version never ran) rewrites each item in that class and
 *   keeps the user signed in;
 * - a reinstall (no marker, this version ran: iOS kept the Keychain) clears the session and
 *   the installation id before anything reads them.
 */
import * as ts from "typescript";

declare const __dirname: string;

const THIS_DEVICE_ONLY = 4;
const DOCS = "file:///docs/";
const MARKER = `${DOCS}recall.install-marker.txt`;
const SESSION = "recall_session_v1";
const RAN = "recall_install_v1";
const INSTALL_ID = "recall_installation_id_v1";

type Item = { value: string; accessible: number | "default" };
const mockKeychain = new Map<string, Item>();
const mockFiles = new Map<string, string>();
const mockKeychainLocked = { now: false };
const mockDiskFull = { now: false };
/** Keys whose writes fail as a full Keychain's do. */
const mockKeychainFull = new Set<string>();
/** The race: the second look at the legacy id file waits until the first call deleted it. */
const mockRace = { on: false, looks: 0, deleted: Promise.resolve(), markDeleted: () => {} };
const mockReport = jest.fn();
const mockLogoutSession = jest.fn(async (..._args: unknown[]) => true);

const mockGetItem = jest.fn(async (key: string, _options?: object) => {
  if (mockKeychainLocked.now) throw new Error("errSecInteractionNotAllowed");
  return mockKeychain.get(key)?.value ?? null;
});
/**
 * As expo-secure-store 58.0.2 does on iOS (`ios/SecureStoreModule.swift`): a new item takes the
 * class it is given (the default without one); a write over an existing item goes to
 * `SecItemUpdate`, which changes the class only when `keychainAccessible` is passed.
 */
const mockSetItem = jest.fn(async (key: string, value: string, options?: { keychainAccessible?: number }) => {
  if (mockKeychainFull.has(key)) throw new Error("errSecNoSpace");
  const existing = mockKeychain.get(key);
  const accessible = options?.keychainAccessible ?? existing?.accessible ?? "default";
  mockKeychain.set(key, { value, accessible });
});
const mockDeleteItem = jest.fn(async (key: string, _options?: object) => {
  mockKeychain.delete(key);
});

jest.mock("expo-secure-store", () => ({
  AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY: 4,
  getItemAsync: (key: string, options?: object) => mockGetItem(key, options),
  setItemAsync: (key: string, value: string, options?: { keychainAccessible?: number }) =>
    mockSetItem(key, value, options),
  deleteItemAsync: (key: string, options?: object) => mockDeleteItem(key, options),
}));
jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "file:///docs/",
  cacheDirectory: "file:///cache/",
  getInfoAsync: jest.fn(async (path: string) => {
    if (mockRace.on && path.endsWith("recall.installation-id.txt") && ++mockRace.looks === 2) await mockRace.deleted;
    return { exists: mockFiles.has(path) };
  }),
  readAsStringAsync: jest.fn(async (path: string) => mockFiles.get(path) ?? ""),
  writeAsStringAsync: jest.fn(async (path: string, contents: string) => {
    if (mockDiskFull.now) throw new Error("ENOSPC");
    mockFiles.set(path, contents);
  }),
  moveAsync: jest.fn(async ({ from, to }: { from: string; to: string }) => {
    mockFiles.set(to, mockFiles.get(from) ?? "");
    mockFiles.delete(from);
  }),
  deleteAsync: jest.fn(async (path: string) => {
    mockFiles.delete(path);
    if (path.endsWith("recall.installation-id.txt")) mockRace.markDeleted();
  }),
}));
jest.mock("react-native", () => ({ Platform: { OS: "ios" } }));
jest.mock("expo-crypto", () => ({ randomUUID: () => "new-install-id" }));
jest.mock("@/lib/sentry", () => ({ reportFailure: (...args: unknown[]) => mockReport(...args) }));
jest.mock("@/lib/api/client", () => ({ logoutSession: (...args: unknown[]) => mockLogoutSession(...args) }));
jest.mock("@/lib/api/connectionFailures", () => ({ onConnectionAnswered: () => () => {} }));
jest.mock("@/lib/foregroundRefresh", () => ({ onAppStateChange: () => () => {} }));
jest.mock("@/lib/onboarding", () => ({}));

type Modules = {
  auth: typeof import("@/lib/auth");
  installationId: typeof import("@/lib/installationId");
  pendingLogout: typeof import("@/lib/pendingLogout");
};

/** The app as a fresh launch loads it: nothing in memory, the disk and Keychain as they were. */
async function launch(): Promise<Modules> {
  jest.resetModules();
  return {
    auth: await import("@/lib/auth"),
    installationId: await import("@/lib/installationId"),
    pendingLogout: await import("@/lib/pendingLogout"),
  };
}

/** What an earlier version left: items in the default class, no marker. */
function oldVersionSignedIn(): void {
  mockKeychain.set(SESSION, {
    value: JSON.stringify({ accessToken: "access-a", refreshToken: "refresh-a" }),
    accessible: "default",
  });
}

beforeEach(() => {
  mockKeychain.clear();
  mockFiles.clear();
  mockKeychainLocked.now = false;
  mockDiskFull.now = false;
  mockKeychainFull.clear();
  mockRace.on = false;
  mockRace.looks = 0;
  mockReport.mockClear();
  mockLogoutSession.mockClear();
  mockGetItem.mockClear();
  mockSetItem.mockClear();
  mockDeleteItem.mockClear();
});

it("passes this-device-only on every secure store read, write and delete", async () => {
  oldVersionSignedIn();
  const { auth, installationId } = await launch();
  await auth.getToken();
  await auth.setTokenPair("access-b", "refresh-b");
  await installationId.getInstallationId();
  await auth.clearToken();
  mockKeychain.set(RAN, { value: "1", accessible: THIS_DEVICE_ONLY });
  mockFiles.delete(MARKER);
  await (await launch()).auth.getToken();

  const calls = [...mockGetItem.mock.calls, ...mockDeleteItem.mock.calls, ...mockSetItem.mock.calls.map(([k, , o]) => [k, o])];
  expect(calls.length).toBeGreaterThan(5);
  expect(calls.filter(([, options]) => (options as { keychainAccessible?: number } | undefined)
    ?.keychainAccessible !== THIS_DEVICE_ONLY)).toEqual([]);
});

it("opens the secure store only through lib/secureStore.ts", () => {
  const root = ts.sys.resolvePath(`${__dirname}/../..`);
  const files = ["app", "components", "contexts", "features", "hooks", "lib", "ui"].flatMap((dir) =>
    ts.sys.readDirectory(`${root}/${dir}`, [".ts", ".tsx"], ["**/__tests__/**", "**/vendor/**"]));
  const importers = files
    .filter((file) => /from "expo-secure-store"/.test(ts.sys.readFile(file) ?? ""))
    .map((file) => file.slice(root.length + 1));
  expect(importers).toEqual(["lib/secureStore.ts"]);
});

it("keeps a signed-in user signed in through the upgrade, and moves the session to this phone only", async () => {
  oldVersionSignedIn();
  const { auth } = await launch();
  await expect(auth.getToken()).resolves.toBe("access-a");
  expect(mockKeychain.get(SESSION)?.accessible).toBe(THIS_DEVICE_ONLY);
  expect(mockFiles.has(MARKER)).toBe(true);
  expect(mockKeychain.get(RAN)?.value).toBe("1");

  // The next launch is an ordinary one: still signed in, nothing rewritten.
  mockSetItem.mockClear();
  await expect((await launch()).auth.getRefreshToken()).resolves.toBe("refresh-a");
  expect(mockSetItem).not.toHaveBeenCalled();
});

it("keeps the session when the first launch is killed between the marker and the Keychain item", async () => {
  oldVersionSignedIn();
  mockFiles.set(MARKER, "1");
  await expect((await launch()).auth.getToken()).resolves.toBe("access-a");
  expect(mockKeychain.get(RAN)?.value).toBe("1");
});

it("clears the session and the installation id on a reinstall", async () => {
  oldVersionSignedIn();
  const first = await launch();
  await first.auth.getToken();
  await expect(first.installationId.getInstallationId()).resolves.toBe("new-install-id");
  mockKeychain.set(INSTALL_ID, { value: "old-install-id", accessible: THIS_DEVICE_ONLY });

  // Deleting the app takes the documents directory; iOS keeps the Keychain.
  mockFiles.clear();
  const reinstalled = await launch();
  await expect(reinstalled.auth.getToken()).resolves.toBeNull();
  expect(mockKeychain.has(SESSION)).toBe(false);
  await expect(reinstalled.installationId.getInstallationId()).resolves.toBe("new-install-id");
  expect(mockFiles.has(MARKER)).toBe(true);

  // Signing in after the reinstall stays signed in at the next launch.
  await reinstalled.auth.setTokenPair("access-c", "refresh-c");
  await expect((await launch()).auth.getToken()).resolves.toBe("access-c");
});

it("changes nothing while the Keychain cannot be read, and checks again on the next call", async () => {
  oldVersionSignedIn();
  // A reinstall launched while the Keychain is locked.
  mockKeychain.set(RAN, { value: "1", accessible: THIS_DEVICE_ONLY });
  mockKeychainLocked.now = true;
  const { auth } = await launch();
  await expect(auth.getToken()).rejects.toThrow();
  expect(mockKeychain.has(SESSION)).toBe(true);
  expect(mockFiles.has(MARKER)).toBe(false);

  mockKeychainLocked.now = false;
  await expect(auth.getToken()).resolves.toBeNull();
  expect(mockFiles.has(MARKER)).toBe(true);
});

it("keeps an upgraded phone's installation id, moved from its documents file into the secure store", async () => {
  mockFiles.set(`${DOCS}recall.installation-id.txt`, " kept-id \n");
  const { installationId } = await launch();
  await expect(installationId.getInstallationId()).resolves.toBe("kept-id");
  expect(mockKeychain.get(INSTALL_ID)).toEqual({ value: "kept-id", accessible: THIS_DEVICE_ONLY });
  expect(mockFiles.has(`${DOCS}recall.installation-id.txt`)).toBe(false);
  await expect((await launch()).installationId.getInstallationId()).resolves.toBe("kept-id");
});

/**
 * The migration rests on expo-secure-store's iOS `set`: a write over an existing item goes to
 * `update`, which puts the requested class in `SecItemUpdate`'s attributes, and the lookup has
 * no class in it, so an item of the old class is the one found and updated. Read from the
 * installed native source, as appStoreConfig.test.ts reads the Android rules.
 */
it("rests on the installed expo-secure-store updating an existing item's class in place", () => {
  const swift = ts.sys.readFile(
    ts.sys.resolvePath(`${__dirname}/../../node_modules/expo-secure-store/ios/SecureStoreModule.swift`),
  ) ?? "";
  const body = (name: string) => swift.slice(swift.indexOf(`private func ${name}(`), swift.indexOf("\n  private func", swift.indexOf(`private func ${name}(`) + 1));
  expect(body("set")).toMatch(/case errSecDuplicateItem:\s*return try update\(value: value, with: key, options: options\)/);
  expect(body("update")).toMatch(/if options\.keychainAccessible != nil \{[\s\S]*updateDictionary\[kSecAttrAccessible\] = attributeWith\(options: options\)/);
  expect(body("update")).toContain("SecItemUpdate(query as CFDictionary, updateDictionary as CFDictionary)");
  expect(body("query")).not.toContain("kSecAttrAccessible");
});

it("on a reinstall, owes the server the old session's logout, which the next start sends", async () => {
  oldVersionSignedIn();
  await (await launch()).auth.getToken();
  mockFiles.clear();

  const reinstalled = await launch();
  await expect(reinstalled.auth.getToken()).resolves.toBeNull();
  const owed = JSON.parse(mockKeychain.get("recall_pending_logouts_v1")?.value ?? "[]") as { accessToken: string }[];
  expect(owed.map((entry) => entry.accessToken)).toEqual(["access-a"]);
  expect(mockKeychain.get("recall_pending_logouts_v1")?.accessible).toBe(THIS_DEVICE_ONLY);

  // No one is signed in, so the logout also takes this device's push token off that account.
  await reinstalled.pendingLogout.retryPendingLogouts(async () => "ExponentPushToken[device]");
  expect(mockLogoutSession).toHaveBeenCalledWith("access-a", "refresh-a", "ExponentPushToken[device]");
  expect(JSON.parse(mockKeychain.get("recall_pending_logouts_v1")?.value ?? "[]")).toEqual([]);
});

it("clears a reinstall once, so a marker that cannot be written never deletes a new sign-in", async () => {
  oldVersionSignedIn();
  mockKeychain.set(RAN, { value: "1", accessible: THIS_DEVICE_ONLY });
  mockDiskFull.now = true;
  const { auth } = await launch();
  await expect(auth.getToken()).resolves.toBeNull();
  expect(mockReport).toHaveBeenCalledWith("install_check", expect.any(Error));

  await auth.setTokenPair("access-new", "refresh-new");
  await expect(auth.getToken()).resolves.toBe("access-new");
  expect(mockFiles.has(MARKER)).toBe(false);
  expect(mockReport).toHaveBeenCalledTimes(1);

  // Relaunched while the disk is still full: no marker, and no "ran" either, so no reinstall.
  const relaunched = await launch();
  await expect(relaunched.auth.getToken()).resolves.toBe("access-new");
  expect(mockFiles.has(MARKER)).toBe(false);

  // Storage frees up: the marker is written and the new sign-in stays.
  mockDiskFull.now = false;
  await expect(relaunched.auth.getToken()).resolves.toBe("access-new");
  expect(mockFiles.has(MARKER)).toBe(true);
  await expect((await launch()).auth.getToken()).resolves.toBe("access-new");
});

it("clears a reinstall's session even when the Keychain is too full to owe its logout", async () => {
  oldVersionSignedIn();
  mockKeychain.set(RAN, { value: "1", accessible: THIS_DEVICE_ONLY });
  mockKeychainFull.add("recall_pending_logouts_v1");
  await expect((await launch()).auth.getToken()).resolves.toBeNull();
  expect(mockKeychain.has(SESSION)).toBe(false);
  expect(mockReport).toHaveBeenCalledWith("install_check", expect.any(Error));
  await expect((await launch()).auth.getToken()).resolves.toBeNull();
});

it("gives callers at once on the first upgraded launch the one id it moved", async () => {
  mockFiles.set(`${DOCS}recall.installation-id.txt`, "kept-id");
  // Two reads of their own: the second looks for the file only after the first deleted it.
  mockRace.on = true;
  mockRace.deleted = new Promise<void>((resolve) => {
    mockRace.markDeleted = resolve;
  });
  const { installationId } = await launch();
  const ids = await Promise.all([installationId.getInstallationId(), installationId.getInstallationId()]);
  expect(ids).toEqual(["kept-id", "kept-id"]);
  expect(mockKeychain.get(INSTALL_ID)?.value).toBe("kept-id");
});

it("keeps the registered push token on this phone only, moved from its documents file", async () => {
  mockFiles.set(`${DOCS}recall.push-token.txt`, "ExponentPushToken[old]\n");
  await launch();
  const { readRegisteredPushToken, rememberRegisteredPushToken } = await import(
    "@/features/notifications/model/registeredPushToken"
  );
  await expect(readRegisteredPushToken()).resolves.toBe("ExponentPushToken[old]");
  expect(mockKeychain.get("recall_push_token_v1")).toEqual({ value: "ExponentPushToken[old]", accessible: THIS_DEVICE_ONLY });
  expect(mockFiles.has(`${DOCS}recall.push-token.txt`)).toBe(false);

  await rememberRegisteredPushToken(null);
  expect(mockKeychain.has("recall_push_token_v1")).toBe(false);
});

it("on a reinstall, owes the old session's logout with the token the deleted app registered, then forgets it", async () => {
  oldVersionSignedIn();
  mockKeychain.set(RAN, { value: "1", accessible: THIS_DEVICE_ONLY });
  mockKeychain.set("recall_push_token_v1", { value: "ExponentPushToken[device]", accessible: THIS_DEVICE_ONLY });
  await expect((await launch()).auth.getToken()).resolves.toBeNull();
  const owed = JSON.parse(mockKeychain.get("recall_pending_logouts_v1")?.value ?? "[]") as { pushToken: string | null }[];
  expect(owed.map((entry) => entry.pushToken)).toEqual(["ExponentPushToken[device]"]);
  expect(mockKeychain.has("recall_push_token_v1")).toBe(false);
});
