import {
  clearSavedComposerDrafts,
  readComposerDrafts,
  writeComposerDrafts,
} from "@/features/chat/model/composerDraftFile";

const mockFiles = new Map<string, string>();
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "/mock-cache/",
  getInfoAsync: jest.fn(async (path: string) => ({ exists: mockFiles.has(path) })),
  readAsStringAsync: jest.fn(async (path: string) => mockFiles.get(path)),
  writeAsStringAsync: jest.fn(async (path: string, contents: string) => { mockFiles.set(path, contents); }),
  deleteAsync: jest.fn(async (path: string) => { mockFiles.delete(path); }),
}));

const PATH = "/mock-cache/recall-composer-drafts.json";

beforeEach(() => mockFiles.clear());

it("reads back each chat's draft this account wrote, and leaves out empty ones", async () => {
  await writeComposerDrafts("user-1", new Map([["new", "Plan a trip"], ["chat-1", "  "], ["chat-2", "and the second"]]));
  const drafts = await readComposerDrafts("user-1");
  expect([...drafts]).toEqual([["new", "Plan a trip"], ["chat-2", "and the second"]]);
});

it("never gives one account another's drafts", async () => {
  await writeComposerDrafts("user-1", new Map([["new", "private"]]));
  expect((await readComposerDrafts("user-2")).size).toBe(0);
});

it("deletes the file when no draft is left, and on sign-out", async () => {
  await writeComposerDrafts("user-1", new Map([["new", "sent soon"]]));
  await writeComposerDrafts("user-1", new Map([["new", ""]]));
  expect(mockFiles.has(PATH)).toBe(false);

  await writeComposerDrafts("user-1", new Map([["new", "kept"]]));
  await clearSavedComposerDrafts();
  expect(mockFiles.has(PATH)).toBe(false);
});

it("keeps the newest fifty", async () => {
  const many = new Map(Array.from({ length: 60 }, (_, index) => [`chat-${index}`, `draft ${index}`] as const));
  await writeComposerDrafts("user-1", many);
  const drafts = await readComposerDrafts("user-1");
  expect(drafts.size).toBe(50);
  expect(drafts.has("chat-9")).toBe(false);
  expect(drafts.get("chat-59")).toBe("draft 59");
});

it("keeps the first 20,000 characters of a longer draft, never half a character", async () => {
  const pasted = `${"a".repeat(19_999)}😀${"b".repeat(5_000)}`;
  await writeComposerDrafts("user-1", new Map([["new", pasted]]));
  const kept = (await readComposerDrafts("user-1")).get("new");
  expect(Array.from(kept ?? "")).toHaveLength(20_000);
  expect(kept?.endsWith("😀")).toBe(true);
});

it("reads an unreadable file as no drafts", async () => {
  mockFiles.set(PATH, "{not json");
  expect((await readComposerDrafts("user-1")).size).toBe(0);
});
