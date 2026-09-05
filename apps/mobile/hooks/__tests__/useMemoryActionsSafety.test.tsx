import React from "react";
import { act, render } from "@testing-library/react-native";
import { useMemoryActions } from "@/hooks/useMemoryActions";
import type { Memory } from "@/lib/api";
import { api } from "@/lib/api";
import { fetchMemories } from "@/lib/cache/memoryListCache";

let mockSession = 1;
let mockCache: Memory[] | undefined;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/lib/api", () => ({ api: {
  deleteMemorySection: jest.fn(), deleteMemoryFact: jest.fn(), updateMemory: jest.fn(),
} }));
jest.mock("@/lib/cache/memoryListCache", () => ({
  fetchMemories: jest.fn(),
  getCachedMemories: () => mockCache,
  setMemoriesCache: (rows: Memory[]) => { mockCache = rows; },
  updateMemoriesCache: (update: (rows: Memory[]) => Memory[], session = mockSession) => {
    if (session === mockSession) mockCache = update(mockCache ?? []);
    return mockCache ?? [];
  },
}));
const mockApi = jest.mocked(api);
const mockFetch = jest.mocked(fetchMemories);
const A: Memory = { id: "a", type: "fact", text: "Likes tea. Likes coffee.",
  confidence: null, created_at: "2026-01-01", updated_at: "2026-01-01" };
const B: Memory = { ...A, id: "b", type: "preference", text: "Reads books." };
let current: ReturnType<typeof useMemoryActions>;
function Probe({ token = "tok" }: { token?: string | null }) {
  const actions = useMemoryActions(token);
  React.useLayoutEffect(() => { current = actions; });
  return null;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
beforeEach(() => {
  jest.resetAllMocks();
  mockSession++;
  mockCache = [A, B];
  mockFetch.mockImplementation(async () => mockCache ?? null);
});

it("keeps independent successful edits when responses arrive in reverse order", async () => {
  const first = deferred<Memory>();
  const second = deferred<Memory>();
  mockApi.updateMemory.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  await render(<Probe />);
  let p1!: Promise<boolean>; let p2!: Promise<boolean>;
  await act(async () => {
    p1 = current.updateMemoryText(A.id, "Tea draft");
    p2 = current.updateMemoryText(B.id, "Book draft");
  });
  await act(async () => { second.resolve({ ...B, text: "Book saved" }); await p2; });
  await act(async () => { first.resolve({ ...A, text: "Tea saved" }); await p1; });
  expect(current.memories.map((row) => row.text)).toEqual(["Tea saved", "Book saved"]);
  expect(mockCache).toEqual(current.memories);
});

it("rolls back only the failed section without resurrecting another deleted section", async () => {
  const first = deferred<void>();
  const second = deferred<void>();
  mockApi.deleteMemorySection.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  await render(<Probe />);
  let p1!: Promise<boolean>; let p2!: Promise<boolean>;
  await act(async () => {
    p1 = current.deleteSection(A.type);
    p2 = current.deleteSection(B.type);
  });
  await act(async () => { second.resolve(); await p2; });
  await act(async () => { first.reject(new Error("offline")); await p1; });
  expect(current.memories).toEqual([A]);
});

it("keeps another section's edit when a fact deletion rolls back", async () => {
  const deletion = deferred<void>();
  mockApi.deleteMemoryFact.mockReturnValue(deletion.promise);
  mockApi.updateMemory.mockResolvedValue({ ...B, text: "Book saved" });
  await render(<Probe />);
  let pending!: Promise<boolean>;
  await act(async () => { pending = current.deleteFact(A, 0, "Likes tea."); });
  await act(async () => { await current.updateMemoryText(B.id, "Book draft"); });
  await act(async () => { deletion.reject(new Error("offline")); await pending; });
  expect(current.memories).toEqual([A, { ...B, text: "Book saved" }]);
});

it("serializes a same-section edit and delete before React rerenders", async () => {
  const editing = deferred<Memory>();
  mockApi.updateMemory.mockReturnValue(editing.promise);
  await render(<Probe />);
  let pending!: Promise<boolean>;
  await act(async () => {
    pending = current.updateMemoryText(A.id, "Tea draft");
    expect(await current.deleteSection(A.type)).toBe(false);
    expect(await current.deleteFact(A, 0, "Likes tea.")).toBe(false);
  });
  expect(mockApi.deleteMemorySection).not.toHaveBeenCalled();
  expect(mockApi.deleteMemoryFact).not.toHaveBeenCalled();
  await act(async () => { editing.resolve({ ...A, text: "Tea saved" }); await pending; });
});

it("deletes the matching current fact when a retained section has an obsolete index", async () => {
  await render(<Probe />);
  mockCache = [{ ...A, text: "New fact. Likes tea. Likes coffee." }, B];
  await act(async () => { await current.load({ force: true }); });
  mockApi.deleteMemoryFact.mockResolvedValue(undefined);
  await act(async () => { await current.deleteFact(A, 0, "Likes tea."); });
  expect(current.memories[0].text).toBe("New fact. Likes coffee.");
});

it("does not delete an unrelated current fact when the selected fact disappeared", async () => {
  await render(<Probe />);
  mockCache = [{ ...A, text: "New fact. Likes coffee." }, B];
  await act(async () => { await current.load({ force: true }); });
  await act(async () => { expect(await current.deleteFact(A, 0, "Likes tea.")).toBe(false); });
  expect(mockApi.deleteMemoryFact).not.toHaveBeenCalled();
  expect(current.memories[0].text).toBe("New fact. Likes coffee.");
});

it("rejects retained mutation and load callbacks immediately after account invalidation", async () => {
  await render(<Probe />);
  const old = current;
  mockSession++;
  mockCache = [B];
  await act(async () => {
    expect(await old.updateMemoryText(A.id, "Old draft")).toBe(false);
    expect(await old.deleteSection(A.type)).toBe(false);
    expect(await old.deleteFact(A, 0, "Likes tea.")).toBe(false);
    await old.load({ force: true });
  });
  expect(mockApi.updateMemory).not.toHaveBeenCalled();
  expect(mockApi.deleteMemorySection).not.toHaveBeenCalled();
  expect(mockApi.deleteMemoryFact).not.toHaveBeenCalled();
  expect(mockFetch).not.toHaveBeenCalled();
  expect(mockCache).toEqual([B]);
});

it("drops a failed old-account mutation and masks old rows after an account switch", async () => {
  const deletion = deferred<void>();
  mockApi.deleteMemorySection.mockReturnValue(deletion.promise);
  const view = await render(<Probe />);
  let pending!: Promise<boolean>;
  await act(async () => { pending = current.deleteSection(A.type); });
  mockSession++;
  mockCache = undefined;
  await view.rerender(<Probe token="next-account" />);
  expect(current.memories).toEqual([]);
  await act(async () => { deletion.reject(new Error("offline")); await pending; });
  expect(mockCache).toBeUndefined();
  expect(current.memories).toEqual([]);
});

it("retains pending edits through a token refresh in the same session", async () => {
  const editing = deferred<Memory>();
  mockApi.updateMemory.mockReturnValue(editing.promise);
  const view = await render(<Probe />);
  let pending!: Promise<boolean>;
  await act(async () => { pending = current.updateMemoryText(A.id, "Tea draft"); });
  await view.rerender(<Probe token="refreshed" />);
  await act(async () => { editing.resolve({ ...A, text: "Tea saved" }); expect(await pending).toBe(true); });
  expect(current.memories[0].text).toBe("Tea saved");
});

it("does not issue retained callbacks after unmount", async () => {
  const view = await render(<Probe />);
  const old = current;
  await view.unmount();
  expect(await old.deleteSection(A.type)).toBe(false);
  await old.load({ force: true });
  expect(mockApi.deleteMemorySection).not.toHaveBeenCalled();
  expect(mockFetch).not.toHaveBeenCalled();
});

it("surfaces a failed refresh while preserving cached rows", async () => {
  mockFetch.mockResolvedValue(null);
  await render(<Probe />);
  await act(async () => { await current.load({ force: true }); });
  expect(current.memories).toEqual([A, B]);
  expect(current.error).toBe(true);
  expect(current.loading).toBe(false);
});

it("ignores an older load after the latest request completed", async () => {
  const first = deferred<Memory[] | null>();
  const second = deferred<Memory[] | null>();
  mockCache = undefined;
  mockFetch.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
  await render(<Probe />);
  let p1!: Promise<void>; let p2!: Promise<void>;
  await act(async () => {
    p1 = current.load();
    p2 = current.load({ silent: true, force: true });
  });
  await act(async () => { mockCache = [B]; second.resolve([B]); await p2; });
  expect(current.loading).toBe(false);
  await act(async () => { first.resolve([A]); await p1; });
  expect(current.memories).toEqual([B]);
});

it("keeps a section locked across visits and paints the previous visit's saved response", async () => {
  const editing = deferred<Memory>();
  mockApi.updateMemory.mockReturnValue(editing.promise);
  const firstView = await render(<Probe />);
  let pending!: Promise<boolean>;
  await act(async () => { pending = current.updateMemoryText(A.id, "Tea draft"); });
  await firstView.unmount();
  await render(<Probe />);
  expect(current.pendingTypes.has(A.type)).toBe(true);
  await act(async () => { expect(await current.updateMemoryText(A.id, "Second draft")).toBe(false); });
  expect(mockApi.updateMemory).toHaveBeenCalledTimes(1);
  await act(async () => {
    editing.resolve({ ...A, text: "Tea saved" });
    expect(await pending).toBe(false);
  });
  expect(current.memories[0].text).toBe("Tea saved");
  expect(current.pendingTypes.has(A.type)).toBe(false);
});

it("preserves facts discovered by a load while fact deletion is pending", async () => {
  const deletion = deferred<void>();
  mockApi.deleteMemoryFact.mockReturnValue(deletion.promise);
  await render(<Probe />);
  let pending!: Promise<boolean>;
  await act(async () => { pending = current.deleteFact(A, 0, "Likes tea."); });
  mockCache = [{ ...A, text: "New fact. Likes tea. Likes coffee." }, B];
  await act(async () => { deletion.resolve(); await pending; });
  expect(current.memories[0].text).toBe("New fact. Likes coffee.");
});

it("restores only the removed fact on failure, preserving discovered facts", async () => {
  const deletion = deferred<void>();
  mockApi.deleteMemoryFact.mockReturnValue(deletion.promise);
  await render(<Probe />);
  let pending!: Promise<boolean>;
  await act(async () => { pending = current.deleteFact(A, 0, "Likes tea."); });
  mockCache = [{ ...A, text: "New fact. Likes coffee." }, B];
  await act(async () => { deletion.reject(new Error("offline")); await pending; });
  expect(current.memories[0].text).toBe("New fact. Likes tea. Likes coffee.");
});

it("does not delete the remaining duplicate when confirming the same fact action", async () => {
  mockCache = [{ ...A, text: "Likes tea. Likes tea. Likes coffee." }];
  mockApi.deleteMemoryFact.mockResolvedValue(undefined);
  await render(<Probe />);
  await act(async () => { await current.deleteFact(A, 0, "Likes tea."); });
  expect(current.memories[0].text).toBe("Likes tea. Likes coffee.");
});

it("reconciles a fact deletion failure after navigation into the current visit", async () => {
  const deletion = deferred<void>();
  mockApi.deleteMemoryFact.mockReturnValue(deletion.promise);
  const firstView = await render(<Probe />);
  let pending!: Promise<boolean>;
  await act(async () => { pending = current.deleteFact(A, 0, "Likes tea."); });
  await firstView.unmount();
  await render(<Probe />);
  const authoritative = [{ ...A, text: "Likes coffee." }, B];
  mockFetch.mockImplementation(async () => {
    mockCache = authoritative;
    return authoritative;
  });
  await act(async () => { deletion.reject(new Error("404")); await pending; });
  expect(mockFetch).toHaveBeenCalledWith("tok", { force: true, afterPending: true });
  expect(current.memories).toEqual(authoritative);
  expect(current.pendingTypes.has(A.type)).toBe(false);
});
