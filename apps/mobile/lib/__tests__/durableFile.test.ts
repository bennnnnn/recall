/**
 * A durable file lives in the documents directory, which the OS never purges, and a write
 * replaces it whole or not at all (`lib/durableFile.ts`). Earlier versions' cache-directory
 * copy is taken over once.
 */
import { writeAsStringAsync } from "expo-file-system/legacy";

const mockPlatform = { OS: "android" };
const mockFiles = new Map<string, string>();
const mockKill = { beforeRename: false };
const mockUnreadable = new Set<string>();

jest.mock("react-native", () => ({ Platform: mockPlatform }));
jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "file:///docs/",
  cacheDirectory: "file:///cache/",
  getInfoAsync: jest.fn(async (path: string) => ({ exists: mockFiles.has(path) })),
  readAsStringAsync: jest.fn(async (path: string) => {
    if (mockUnreadable.has(path)) throw new Error("EIO");
    return mockFiles.get(path) ?? "";
  }),
  writeAsStringAsync: jest.fn(async (path: string, contents: string) => {
    mockFiles.set(path, contents);
  }),
  moveAsync: jest.fn(async ({ from, to }: { from: string; to: string }) => {
    if (mockKill.beforeRename) throw new Error("killed");
    mockFiles.set(to, mockFiles.get(from) ?? "");
    mockFiles.delete(from);
  }),
  deleteAsync: jest.fn(async (path: string) => {
    mockFiles.delete(path);
  }),
}));

type Module = typeof import("@/lib/durableFile");

/** A fresh launch: nothing in memory, the files as they were. */
function launch(): Module {
  let loaded!: Module;
  jest.isolateModules(() => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- a fresh copy per launch
    loaded = require("@/lib/durableFile") as Module;
  });
  return loaded;
}

const DOC = "file:///docs/drafts.json";
const TEMP = `${DOC}.tmp`;
const CACHE = "file:///cache/drafts.json";

beforeEach(() => {
  mockFiles.clear();
  mockKill.beforeRename = false;
  mockUnreadable.clear();
  mockPlatform.OS = "android";
  (writeAsStringAsync as jest.Mock).mockClear();
});

it("writes in the documents directory, not the purgeable cache", async () => {
  await launch().durableFile("drafts.json").write("kept");
  expect([...mockFiles.keys()]).toEqual([DOC]);
});

it("keeps the old file when Android is killed between the temp write and the rename", async () => {
  const file = launch().durableFile("drafts.json");
  await file.write("old");
  mockKill.beforeRename = true;
  await file.write("new, cut short");
  expect(mockFiles.get(DOC)).toBe("old");
  expect(mockFiles.has(TEMP)).toBe(true);

  // The next launch reads the old file and never the stray temp.
  mockKill.beforeRename = false;
  const relaunched = launch().durableFile("drafts.json");
  await expect(relaunched.read()).resolves.toBe("old");
  await relaunched.write("newer");
  await expect(relaunched.read()).resolves.toBe("newer");
});

it("never reads a stray temp file when no file was written yet", async () => {
  mockFiles.set(TEMP, "{\"half");
  await expect(launch().durableFile("drafts.json").read()).resolves.toBeNull();
});

it("writes in place on iOS, whose native write is already atomic", async () => {
  mockPlatform.OS = "ios";
  await launch().durableFile("drafts.json").write("kept");
  expect((writeAsStringAsync as jest.Mock).mock.calls).toEqual([[DOC, "kept"]]);
});

it("takes over the cache-directory copy an earlier version wrote, once", async () => {
  mockFiles.set(CACHE, "from the cache");
  const file = launch().durableFile("drafts.json", "drafts.json");
  await expect(file.read()).resolves.toBe("from the cache");
  expect(mockFiles.get(DOC)).toBe("from the cache");
  expect(mockFiles.has(CACHE)).toBe(false);
});

it("keeps its own file over a stale cache copy, and deletes the copy", async () => {
  mockFiles.set(DOC, "durable");
  mockFiles.set(CACHE, "stale");
  await expect(launch().durableFile("drafts.json", "drafts.json").read()).resolves.toBe("durable");
  expect(mockFiles.has(CACHE)).toBe(false);
});

it("takes over the cache copy before a first write, so the write wins", async () => {
  mockFiles.set(CACHE, "from the cache");
  const file = launch().durableFile("drafts.json", "drafts.json");
  await file.write("typed this run");
  await expect(file.read()).resolves.toBe("typed this run");
  expect(mockFiles.has(CACHE)).toBe(false);
});

it("clears the file, its temp and the cache copy (sign-out)", async () => {
  mockFiles.set(DOC, "a");
  mockFiles.set(TEMP, "b");
  mockFiles.set(CACHE, "c");
  await launch().durableFile("drafts.json", "drafts.json").clear();
  expect(mockFiles.size).toBe(0);
});

it("never adopts or deletes a cache copy it could not read, and joins it in once it reads", async () => {
  mockFiles.set(CACHE, "old drafts");
  mockUnreadable.add(CACHE);
  const join = (current: string, former: string) => `${current} + ${former}`;
  const file = launch().durableFile("drafts.json", "drafts.json", join);
  await expect(file.read()).resolves.toBeNull();
  await file.write("typed this run");
  expect(mockFiles.get(CACHE)).toBe("old drafts");

  // A later run reads the copy: it is joined into this version's file, then deleted.
  mockUnreadable.clear();
  await expect(launch().durableFile("drafts.json", "drafts.json", join).read()).resolves.toBe("typed this run + old drafts");
  expect(mockFiles.has(CACHE)).toBe(false);
});
