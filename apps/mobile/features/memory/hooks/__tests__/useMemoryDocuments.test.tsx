import { act, renderHook } from "@testing-library/react-native";

import { useMemoryDocuments } from "@/features/memory/hooks/useMemoryDocuments";
import {
  getCachedMemoryDocuments,
  invalidateMemoryDocuments,
  setMemoryDocuments,
} from "@/features/memory/model/memoryDocumentsCache";
import type { MemoryDocument } from "@/features/memory/types";
import { api } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  api: {
    deleteMemory: jest.fn(),
    deleteMemoryDocument: jest.fn(),
    listMemoryDocuments: jest.fn(),
  },
}));
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => 1,
  requireTokenSession: () => undefined,
}));
jest.mock("@/features/memory/model/memoryListCache", () => ({ invalidateMemoriesCache: jest.fn() }));

function fact(id: string) {
  return {
    id,
    type: "fact",
    text: `Fact ${id}`,
    confidence: 0.9,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
  };
}

function page(key: string, ...factIds: string[]): MemoryDocument {
  return {
    key,
    group: "topics",
    title: key,
    summary: "",
    updated_at: null,
    facts: factIds.map(fact),
  };
}

function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function shown() {
  return (getCachedMemoryDocuments()?.documents ?? []).map((document) => [
    document.key,
    document.facts.map((item) => item.id),
  ]);
}

beforeEach(() => {
  jest.clearAllMocks();
  invalidateMemoryDocuments();
  setMemoryDocuments({ scanning: false, documents: [page("interests", "a", "b"), page("notes", "c")] }, 1);
});

describe("useMemoryDocuments deletes", () => {
  it("puts back only the delete that failed when two overlap", async () => {
    const factDelete = deferred();
    const pageDelete = deferred();
    (api.deleteMemory as jest.Mock).mockReturnValue(factDelete.promise);
    (api.deleteMemoryDocument as jest.Mock).mockReturnValue(pageDelete.promise);
    const { result } = await renderHook(() => useMemoryDocuments("token"));

    let factDone!: Promise<boolean>;
    let pageDone!: Promise<boolean>;
    await act(async () => {
      factDone = result.current.deleteFact("a");
      pageDone = result.current.deleteDocument("notes");
    });
    expect(shown()).toEqual([["interests", ["b"]]]);

    await act(async () => {
      pageDelete.resolve();
      await pageDone;
      factDelete.reject(new Error("offline"));
      await factDone;
    });

    await expect(factDone).resolves.toBe(false);
    await expect(pageDone).resolves.toBe(true);
    // The page delete went through, so only fact "a" comes back, in its old place.
    expect(shown()).toEqual([["interests", ["a", "b"]]]);
  });

  it("brings back a failed page without undoing a fact delete that went through", async () => {
    (api.deleteMemoryDocument as jest.Mock).mockRejectedValue(new Error("offline"));
    (api.deleteMemory as jest.Mock).mockResolvedValue(undefined);
    const { result } = await renderHook(() => useMemoryDocuments("token"));

    await act(async () => {
      await Promise.all([result.current.deleteDocument("notes"), result.current.deleteFact("b")]);
    });

    expect(shown()).toEqual([
      ["interests", ["a"]],
      ["notes", ["c"]],
    ]);
  });

  it("brings back a page that emptied with its last fact", async () => {
    (api.deleteMemory as jest.Mock).mockRejectedValue(new Error("offline"));
    const { result } = await renderHook(() => useMemoryDocuments("token"));

    let ok = true;
    await act(async () => {
      ok = await result.current.deleteFact("c");
    });

    expect(ok).toBe(false);
    expect(shown()).toEqual([
      ["interests", ["a", "b"]],
      ["notes", ["c"]],
    ]);
  });

  it("keeps a deleted fact gone when a refresh lands mid-request", async () => {
    const factDelete = deferred();
    (api.deleteMemory as jest.Mock).mockReturnValue(factDelete.promise);
    const { result } = await renderHook(() => useMemoryDocuments("token"));

    let done!: Promise<boolean>;
    await act(async () => {
      done = result.current.deleteFact("a");
    });
    // A poll answered before the server deleted the fact.
    setMemoryDocuments({ scanning: true, documents: [page("interests", "a", "b"), page("notes", "c")] }, 1);
    await act(async () => {
      factDelete.resolve();
      await done;
    });

    expect(shown()).toEqual([
      ["interests", ["b"]],
      ["notes", ["c"]],
    ]);
  });
});
