/**
 * The installation id lives in the secure store, this phone only (`lib/installationId.ts`);
 * an earlier version's documents file is moved there once.
 */
import * as Crypto from "expo-crypto";

import { getInstallationId } from "@/lib/installationId";

const mockKeychain = new Map<string, string>();
const mockFiles = new Map<string, string>();
const mockKeychainFails = { now: false };

jest.mock("expo-crypto", () => ({
  randomUUID: jest.fn(() => "install-uuid-1"),
}));
jest.mock("expo-secure-store", () => ({
  AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY: 4,
  getItemAsync: jest.fn(async (key: string) => {
    if (mockKeychainFails.now) throw new Error("errSecMissingEntitlement");
    return mockKeychain.get(key) ?? null;
  }),
  setItemAsync: jest.fn(async (key: string, value: string) => {
    if (mockKeychainFails.now) throw new Error("errSecMissingEntitlement");
    mockKeychain.set(key, value);
  }),
  deleteItemAsync: jest.fn(async (key: string) => {
    mockKeychain.delete(key);
  }),
}));
// No documents directory for the launch's install check (lib/secureStore.ts has its own tests).
jest.mock("@/lib/durableFile", () => {
  throw new Error("not loaded here");
});
jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "file:///docs/",
  getInfoAsync: jest.fn(async (path: string) => ({ exists: mockFiles.has(path) })),
  readAsStringAsync: jest.fn(async (path: string) => mockFiles.get(path) ?? ""),
  deleteAsync: jest.fn(async (path: string) => {
    mockFiles.delete(path);
  }),
}));
jest.mock("@/lib/sentry", () => ({ reportFailure: jest.fn() }));

const KEY = "recall_installation_id_v1";
const LEGACY = "file:///docs/recall.installation-id.txt";

describe("getInstallationId", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockKeychain.clear();
    mockFiles.clear();
    mockKeychainFails.now = false;
  });

  it("returns the id the secure store holds", async () => {
    mockKeychain.set(KEY, "existing-id");
    await expect(getInstallationId()).resolves.toBe("existing-id");
    expect(Crypto.randomUUID).not.toHaveBeenCalled();
  });

  it("creates and keeps a new id when there is none", async () => {
    await expect(getInstallationId()).resolves.toBe("install-uuid-1");
    expect(mockKeychain.get(KEY)).toBe("install-uuid-1");
    expect(mockFiles.size).toBe(0);
  });

  it("moves an earlier version's id from its documents file", async () => {
    mockFiles.set(LEGACY, "  existing-id  ");
    await expect(getInstallationId()).resolves.toBe("existing-id");
    expect(mockKeychain.get(KEY)).toBe("existing-id");
    expect(mockFiles.has(LEGACY)).toBe(false);
    expect(Crypto.randomUUID).not.toHaveBeenCalled();
  });

  it("reads the file's id where the secure store cannot be used, and makes none", async () => {
    mockKeychainFails.now = true;
    await expect(getInstallationId()).resolves.toBeNull();
    mockFiles.set(LEGACY, "file-id");
    await expect(getInstallationId()).resolves.toBe("file-id");
    expect(mockFiles.has(LEGACY)).toBe(true);
  });
});
