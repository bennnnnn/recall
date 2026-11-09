import { act, renderHook } from "@testing-library/react-native";

import { useChatPageSync } from "@/features/chat/hooks/useChatPageCacheWriter";
import { chatPageReadAt, clearChatPageReads } from "@/features/chat/model/pageReads";

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0 }));
jest.mock("@/lib/api", () => ({ api: {} }));
jest.mock("@/features/chat/model/chatListCache", () => ({ getCachedChat: () => undefined }));
// The page store's file is not under test.
jest.mock("expo-file-system/legacy", () => ({ cacheDirectory: null }));

beforeEach(() => clearChatPageReads());

describe("useChatPageSync", () => {
  it("rests the thread on a page that landed and notes it as the chat's newest read", async () => {
    const { result } = await renderHook(() => useChatPageSync());
    await act(async () => result.current.notePageRead("chat-a", 1_000));
    expect(result.current.sync).toEqual({ chatId: "chat-a", fetchedAt: 1_000 });
    expect(chatPageReadAt("chat-a")).toBe(1_000);
  });

  it("notes a page with no time given as read now, the same moment in both records", async () => {
    const now = jest.spyOn(Date, "now").mockReturnValue(5_000);
    try {
      const { result } = await renderHook(() => useChatPageSync());
      await act(async () => result.current.notePageRead("chat-a"));
      expect(result.current.sync).toEqual({ chatId: "chat-a", fetchedAt: 5_000 });
      expect(chatPageReadAt("chat-a")).toBe(5_000);
    } finally {
      now.mockRestore();
    }
  });

  it("rests nothing on a page left unmerged, and notes no read for it", async () => {
    const { result } = await renderHook(() => useChatPageSync());
    await act(async () => result.current.notePageUnmerged("chat-a"));
    expect(result.current.sync).toEqual({ chatId: "chat-a", fetchedAt: null });
    expect(chatPageReadAt("chat-a")).toBeUndefined();

    await act(async () => result.current.clearPageSync());
    expect(result.current.sync).toBeNull();
  });
});
