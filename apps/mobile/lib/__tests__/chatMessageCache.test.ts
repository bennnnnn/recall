jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "/mock-cache/",
  getInfoAsync: jest.fn(),
  makeDirectoryAsync: jest.fn(),
  readAsStringAsync: jest.fn(),
  writeAsStringAsync: jest.fn(),
  deleteAsync: jest.fn(),
}));

import {
  clearCachedChatMessages,
  readCachedChatMessages,
  writeCachedChatMessages,
} from "@/lib/chatMessageCache";
import type { Message } from "@/lib/api";
import {
  deleteAsync,
  getInfoAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";

const messages: Message[] = [
  { id: "m1", role: "user", content: "Hi", model: null, created_at: "2026-01-01T00:00:00Z" },
];

describe("chatMessageCache", () => {
  beforeEach(() => {
    jest.clearAllMocks();
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
});
