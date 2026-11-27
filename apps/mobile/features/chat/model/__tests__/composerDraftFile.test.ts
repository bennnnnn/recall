import {
  clearSavedComposerDrafts,
  readComposerDrafts,
  writeComposerDrafts,
} from "@/features/chat/model/composerDraftFile";
import { isPadMathDraft, notePadMathDraft } from "@/features/chat/model/padMathDrafts";

const mockFiles = new Map<string, string>();
jest.mock("react-native", () => ({ Platform: { OS: "android" } }));
jest.mock("expo-file-system/legacy", () => ({
  documentDirectory: "/mock-docs/",
  cacheDirectory: "/mock-cache/",
  moveAsync: jest.fn(async ({ from, to }: { from: string; to: string }) => {
    mockFiles.set(to, mockFiles.get(from) ?? "");
    mockFiles.delete(from);
  }),
  getInfoAsync: jest.fn(async (path: string) => ({ exists: mockFiles.has(path) })),
  readAsStringAsync: jest.fn(async (path: string) => mockFiles.get(path)),
  writeAsStringAsync: jest.fn(async (path: string, contents: string) => { mockFiles.set(path, contents); }),
  deleteAsync: jest.fn(async (path: string) => { mockFiles.delete(path); }),
}));

const PATH = "/mock-docs/recall-composer-drafts.json";
const CACHE_PATH = "/mock-cache/recall-composer-drafts.json";

beforeEach(() => mockFiles.clear());

it("reads back each chat's draft this account wrote, and leaves out empty ones", async () => {
  await writeComposerDrafts("user-1", new Map([["new", "Plan a trip"], ["chat-1", "  "], ["chat-2", "and the second"]]));
  const drafts = await readComposerDrafts("user-1");
  expect([...drafts]).toEqual([["new", "Plan a trip"], ["chat-2", "and the second"]]);
});

// A math draft saved as the app closed came back as `$\frac{5}{3}$` in the field.
it("remembers which drafts the math keyboard wrote, and only those", async () => {
  notePadMathDraft("$\\frac{5}{3}$");
  await writeComposerDrafts("user-1", new Map([["new", "$\\frac{5}{3}$"], ["chat-1", "The price is $5"]]));
  expect(JSON.parse(mockFiles.get(PATH) ?? "{}").math).toEqual(["new"]);
  await clearSavedComposerDrafts();
  expect(isPadMathDraft("$\\frac{5}{3}$")).toBe(false);

  mockFiles.set(PATH, JSON.stringify({ user_id: "user-1", drafts: { new: "$x^2$", "chat-1": "The price is $5" }, math: ["new"] }));
  await readComposerDrafts("user-1");
  expect(isPadMathDraft("$x^2$")).toBe(true);
  expect(isPadMathDraft("The price is $5")).toBe(false);
  await clearSavedComposerDrafts();
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

// The cache directory is purged when storage runs low; the drafts moved to the documents directory.
it("keeps the drafts an earlier version wrote in the cache directory, and moves them", async () => {
  jest.resetModules();
  mockFiles.set(CACHE_PATH, JSON.stringify({ user_id: "user-1", drafts: { new: "before the upgrade" } }));
  const upgraded = await import("@/features/chat/model/composerDraftFile");
  expect([...(await upgraded.readComposerDrafts("user-1"))]).toEqual([["new", "before the upgrade"]]);
  expect(mockFiles.has(CACHE_PATH)).toBe(false);
  expect(mockFiles.has(PATH)).toBe(true);
});
