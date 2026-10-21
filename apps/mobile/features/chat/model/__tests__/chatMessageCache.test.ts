jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "/mock-cache/",
  getInfoAsync: jest.fn(),
  makeDirectoryAsync: jest.fn(),
  readAsStringAsync: jest.fn(),
  writeAsStringAsync: jest.fn(),
  deleteAsync: jest.fn(),
  readDirectoryAsync: jest.fn(async () => []),
}));

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
let mockSession = 0;

import {
  clearAllCachedChatMessages,
  cachedChatPageFetchedAt,
  clearCachedChatMessages,
  patchCachedChatMessage,
  readCachedChatMessages,
  sweepCachedChatPages,
  writeCachedChatMessages,
} from "@/features/chat/model/messageCache";
import type { Message } from "@/lib/api";
import {
  deleteAsync,
  getInfoAsync,
  readAsStringAsync,
  readDirectoryAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";

const messages: Message[] = [
  { id: "m1", role: "user", content: "Hi", model: null, created_at: "2026-01-01T00:00:00Z" },
];

describe("chatMessageCache", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession = 0;
  });

  it("returns null when cache file is missing", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: false });
    await expect(readCachedChatMessages("chat-1")).resolves.toBeNull();
  });

  it("reads cached messages when present", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(
      JSON.stringify({ messages, has_more: false, cached_at: "2026-01-01T00:00:00Z" }),
    );
    await expect(readCachedChatMessages("chat-1")).resolves.toEqual({
      messages,
      has_more: false,
      cached_at: "2026-01-01T00:00:00Z",
    });
  });

  it("writes cached messages to disk", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    await writeCachedChatMessages("chat-1", messages, true);
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "/mock-cache/chat-pages/chat-1.json",
      expect.stringContaining('"has_more":true'),
    );
  });

  it("clears cached messages", async () => {
    await clearCachedChatMessages("chat-1");
    expect(deleteAsync).toHaveBeenCalledWith("/mock-cache/chat-pages/chat-1.json", {
      idempotent: true,
    });
  });

  it("patches one cached message without dropping has_more", async () => {
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (readAsStringAsync as jest.Mock).mockResolvedValue(
      JSON.stringify({
        messages: [
          { id: "m1", role: "assistant", content: "old", model: null, created_at: "2026-01-01T00:00:00Z" },
        ],
        has_more: true,
        cached_at: "2026-01-01T00:00:00.000Z",
      }),
    );
    await patchCachedChatMessage("chat-1", "m1", { content: "new" });
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "/mock-cache/chat-pages/chat-1.json",
      expect.stringContaining('"content":"new"'),
    );
    expect(writeAsStringAsync).toHaveBeenCalledWith(
      "/mock-cache/chat-pages/chat-1.json",
      expect.stringContaining('"has_more":true'),
    );
  });

  it("parses cached_at for the silent-refetch stale window", () => {
    expect(cachedChatPageFetchedAt({ cached_at: "2026-01-01T00:00:00.000Z" })).toBe(
      Date.parse("2026-01-01T00:00:00.000Z"),
    );
    expect(cachedChatPageFetchedAt({ cached_at: "nope" })).toBeUndefined();
    expect(cachedChatPageFetchedAt(null)).toBeUndefined();
  });
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("saved history invalidation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession = 0;
    (getInfoAsync as jest.Mock).mockResolvedValue({ exists: true });
    (writeAsStringAsync as jest.Mock).mockResolvedValue(undefined);
    (deleteAsync as jest.Mock).mockResolvedValue(undefined);
  });

  it.each([false, true])("does not recreate a cleared cache while preparing a write (all: %s)", async (all) => {
    const info = deferred<{ exists: boolean }>();
    (getInfoAsync as jest.Mock).mockReturnValueOnce(info.promise);
    const writing = writeCachedChatMessages("chat-1", messages, false);
    await Promise.resolve();
    const clearing = all ? clearAllCachedChatMessages() : clearCachedChatMessages("chat-1");
    info.resolve({ exists: true });
    await Promise.all([writing, clearing]);
    expect(writeAsStringAsync).not.toHaveBeenCalled();
    expect(deleteAsync).toHaveBeenCalled();
  });

  it("orders deletion after an already-started disk write", async () => {
    const disk = deferred<void>();
    (writeAsStringAsync as jest.Mock).mockReturnValueOnce(disk.promise);
    const writing = writeCachedChatMessages("chat-1", messages, false);
    for (let i = 0; i < 10; i++) await Promise.resolve();
    expect(writeAsStringAsync).toHaveBeenCalled();
    const clearing = clearCachedChatMessages("chat-1");
    await Promise.resolve();
    expect(deleteAsync).not.toHaveBeenCalled();
    disk.resolve();
    await Promise.all([writing, clearing]);
    expect(deleteAsync).toHaveBeenCalled();
  });

  it("discards a read that finishes after the chat cache is cleared", async () => {
    const disk = deferred<string>();
    (readAsStringAsync as jest.Mock).mockReturnValueOnce(disk.promise);
    const reading = readCachedChatMessages("chat-1");
    await Promise.resolve();
    const clearing = clearCachedChatMessages("chat-1");
    disk.resolve(JSON.stringify({ messages, has_more: false, cached_at: "2026-01-01" }));
    await expect(reading).resolves.toBeNull();
    await clearing;
  });

  it("discards writes from a session that ended during file preparation", async () => {
    const info = deferred<{ exists: boolean }>();
    (getInfoAsync as jest.Mock).mockReturnValueOnce(info.promise);
    const writing = writeCachedChatMessages("chat-1", messages, false);
    await Promise.resolve();
    mockSession++;
    info.resolve({ exists: true });
    await writing;
    expect(writeAsStringAsync).not.toHaveBeenCalled();
  });

  it("does not let an older message patch overwrite a newer fetched page", async () => {
    const disk = deferred<string>();
    (readAsStringAsync as jest.Mock).mockReturnValueOnce(disk.promise);
    const patching = patchCachedChatMessage("chat-1", "m1", { content: "Patched" });
    for (let i = 0; i < 10; i++) await Promise.resolve();
    const latest = [...messages, { ...messages[0], id: "m2", content: "Latest saved reply" }];
    const writing = writeCachedChatMessages("chat-1", latest, false);
    disk.resolve(JSON.stringify({ messages, has_more: true, cached_at: "2026-01-01" }));
    await Promise.all([patching, writing]);
    const writes = (writeAsStringAsync as jest.Mock).mock.calls;
    expect(JSON.parse(writes[writes.length - 1][1]).messages).toEqual(latest);
  });

  it("preserves the page fetch time when patching one message", async () => {
    (readAsStringAsync as jest.Mock).mockResolvedValue(JSON.stringify({
      messages, has_more: true, cached_at: "2026-01-01T00:00:00Z",
    }));
    await patchCachedChatMessage("chat-1", "m1", { content: "Updated" });
    expect(JSON.parse((writeAsStringAsync as jest.Mock).mock.calls[0][1])).toEqual({
      messages: [{ ...messages[0], content: "Updated" }], has_more: true,
      cached_at: "2026-01-01T00:00:00Z",
    });
  });
});


describe("chat page sweep (LEAK-07)", () => {
  beforeEach(() => jest.clearAllMocks());

  it("keeps the newest 100 chats and none older than 30 days", async () => {
    const now = Date.parse("2026-10-21T00:00:00Z");
    const day = 24 * 60 * 60_000;
    // chat-0 is the newest, then chat-1 and so on; chat-5 was last opened 31 days ago,
    // so the newest 100 are chat-0 to chat-100 without it.
    const names = Array.from({ length: 102 }, (_, index) => `chat-${index}.json`);
    (readDirectoryAsync as jest.Mock).mockResolvedValueOnce(names);
    (getInfoAsync as jest.Mock).mockImplementation(async (path: string) => {
      const index = Number(path.match(/chat-(\d+)\.json$/)?.[1]);
      const age = index === 5 ? 31 * day : index * 60_000;
      return { exists: true, modificationTime: (now - age) / 1000 };
    });
    await sweepCachedChatPages(now);
    const deleted = (deleteAsync as jest.Mock).mock.calls.map(([path]) => path).sort();
    expect(deleted).toEqual([
      "/mock-cache/chat-pages/chat-101.json",
      "/mock-cache/chat-pages/chat-5.json",
    ]);
  });
});
