import {
  fetchMemoryDocuments,
  getCachedMemoryDocuments,
  invalidateMemoryDocuments,
  setMemoryDocuments,
  subscribeMemoryDocuments,
  updateMemoryDocuments,
} from "@/features/memory/model/memoryDocumentsCache";

import type { MemoryDocuments } from "@/features/memory/types";

let mockSession = 1;
const mockList = jest.fn();

jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockSession,
  requireTokenSession: () => undefined,
}));
jest.mock("@/lib/api", () => ({ api: { listMemoryDocuments: (...args: unknown[]) => mockList(...args) } }));

const pages: MemoryDocuments = {
  scanning: false,
  documents: [
    { key: "profile", group: "you", title: "Profile", summary: "", updated_at: null, facts: [] },
  ],
};

beforeEach(() => {
  mockSession = 1;
  mockList.mockReset();
  invalidateMemoryDocuments();
});

describe("memory documents cache", () => {
  it("shares one read between screens and notifies listeners", async () => {
    let resolve: (value: MemoryDocuments) => void = () => {};
    mockList.mockReturnValue(new Promise<MemoryDocuments>((done) => { resolve = done; }));
    const listener = jest.fn();
    const unsubscribe = subscribeMemoryDocuments(listener);

    const first = fetchMemoryDocuments("token");
    const second = fetchMemoryDocuments("token");
    resolve(pages);

    await expect(first).resolves.toEqual(pages);
    await expect(second).resolves.toEqual(pages);
    expect(mockList).toHaveBeenCalledTimes(1);
    expect(getCachedMemoryDocuments()).toEqual(pages);
    expect(listener).toHaveBeenCalled();
    unsubscribe();
  });

  it("drops a read that finishes after an account switch", async () => {
    let resolve: (value: MemoryDocuments) => void = () => {};
    mockList.mockReturnValue(new Promise<MemoryDocuments>((done) => { resolve = done; }));
    const read = fetchMemoryDocuments("token-a");
    mockSession = 2;
    resolve(pages);

    await expect(read).resolves.toBeNull();
    expect(getCachedMemoryDocuments()).toBeUndefined();
  });

  it("ignores writes meant for another account", () => {
    setMemoryDocuments(pages, 1);
    mockSession = 2;
    setMemoryDocuments(pages, 1);
    updateMemoryDocuments(() => [], 1);
    expect(getCachedMemoryDocuments()).toBeUndefined();
  });

  it("applies a page update for the same account", () => {
    setMemoryDocuments(pages, 1);
    updateMemoryDocuments((documents) => documents.filter((doc) => doc.key !== "profile"), 1);
    expect(getCachedMemoryDocuments()?.documents).toEqual([]);
  });
});
