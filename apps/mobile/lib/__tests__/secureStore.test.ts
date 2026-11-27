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

const mockGetItem = jest.fn(async (key: string, _options?: object) => {
  if (mockKeychainLocked.now) throw new Error("errSecInteractionNotAllowed");
  return mockKeychain.get(key)?.value ?? null;
});
const mockSetItem = jest.fn(async (key: string, value: string, options?: { keychainAccessible?: number }) => {
  mockKeychain.set(key, { value, accessible: options?.keychainAccessible ?? "default" });
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
  getInfoAsync: jest.fn(async (path: string) => ({ exists: mockFiles.has(path) })),
  readAsStringAsync: jest.fn(async (path: string) => mockFiles.get(path) ?? ""),
  writeAsStringAsync: jest.fn(async (path: string, contents: string) => {
    mockFiles.set(path, contents);
  }),
  moveAsync: jest.fn(async ({ from, to }: { from: string; to: string }) => {
    mockFiles.set(to, mockFiles.get(from) ?? "");
    mockFiles.delete(from);
  }),
  deleteAsync: jest.fn(async (path: string) => {
    mockFiles.delete(path);
  }),
}));
jest.mock("react-native", () => ({ Platform: { OS: "ios" } }));
jest.mock("expo-crypto", () => ({ randomUUID: () => "new-install-id" }));
jest.mock("@/lib/sentry", () => ({ reportFailure: jest.fn() }));
jest.mock("@/lib/onboarding", () => ({}));

type Modules = {
  auth: typeof import("@/lib/auth");
  installationId: typeof import("@/lib/installationId");
};

/** The app as a fresh launch loads it: nothing in memory, the disk and Keychain as they were. */
async function launch(): Promise<Modules> {
  jest.resetModules();
  return {
    auth: await import("@/lib/auth"),
    installationId: await import("@/lib/installationId"),
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
