import { act, renderHook } from "@testing-library/react-native";

import { useChatMetadata } from "@/features/chat/hooks/useChatMetadata";
import type { Chat } from "@/lib/api";
import { seedChatListCacheForTest } from "@/features/chat/model/chatListCache";
import { emptyChatList } from "@/features/chat/model/listSections";

let mockSession = 0;
let mockChatChange: ((id: string, patch: Record<string, unknown> | null) => void) | undefined;
jest.mock("@/lib/auth", () => ({
  getSessionGeneration: () => mockSession,
  requireTokenSession: jest.fn(),
  SessionChangedError: class SessionChangedError extends Error {},
}));
jest.mock("@/lib/api", () => ({ api: { listChats: jest.fn() } }));
jest.mock("@/features/chat/model/chatListFile", () => ({
  readStoredChatList: jest.fn(async () => null),
  writeStoredChatList: jest.fn(async () => undefined),
  clearStoredChatList: jest.fn(async () => undefined),
}));
jest.mock("@/features/chat/drawer/drawer", () => ({
  subscribeChatChanges: (fn: typeof mockChatChange) => {
    mockChatChange = fn;
    return () => {
      mockChatChange = undefined;
    };
  },
}));

const row = { id: "chat-a", title: "Trip", pinned: true, archived: true } as Chat;

beforeEach(() => {
  mockSession = 0;
  seedChatListCacheForTest(emptyChatList());
  mockChatChange = undefined;
});

describe("useChatMetadata", () => {
  it("takes the open chat's row, and puts every flag back when the chat is left", async () => {
    const { result } = await renderHook(() => useChatMetadata("chat-a"));
    await act(async () => result.current.applyMetadata(row));
    expect(result.current).toMatchObject({ chatTitle: "Trip", pinned: true, archived: true });

    await act(async () => result.current.resetMetadata());
    expect(result.current).toMatchObject({ chatTitle: null, pinned: false, archived: false });
  });

  it("leaves the flags as they are for a chat the drawer has no row for", async () => {
    const { result } = await renderHook(() => useChatMetadata("chat-a"));
    await act(async () => result.current.applyMetadata(row));
    await act(async () => result.current.applyMetadata(undefined));
    expect(result.current).toMatchObject({ chatTitle: "Trip", pinned: true, archived: true });
  });

  // Pre-launch review 2026-11-27: renamed and archived on another device, the open chat kept
  // its old title and flags in the header and menu until it was opened again.
  it("follows the drawer list's row for the open chat when a read brings a change", async () => {
    const listed = { ...row, title: "Trip", pinned: false, archived: false, updated_at: "2026-11-01T00:00:00Z" };
    seedChatListCacheForTest({ ...emptyChatList(), today: [listed] });
    const { result } = await renderHook(() => useChatMetadata("chat-a"));
    await act(async () => result.current.applyMetadata(listed));
    expect(result.current).toMatchObject({ chatTitle: "Trip", pinned: false, archived: false });

    // The drawer's next read: renamed and archived on the laptop.
    await act(async () => seedChatListCacheForTest({
      ...emptyChatList(), archived: [{ ...listed, title: "Trip to Rome", archived: true }],
    }));
    expect(result.current).toMatchObject({ chatTitle: "Trip to Rome", pinned: false, archived: true });
  });

  it("keeps its own title while the list's row has none yet", async () => {
    seedChatListCacheForTest({ ...emptyChatList(), today: [{ ...row, title: null, pinned: false, archived: false } as unknown as Chat] });
    const { result } = await renderHook(() => useChatMetadata("chat-a"));
    await act(async () => result.current.setChatTitle("Streamed title"));
    expect(result.current.chatTitle).toBe("Streamed title");
  });

  it("follows the drawer's edits to the open chat only, and none from the last account", async () => {
    const { result } = await renderHook(() => useChatMetadata("chat-a"));
    await act(async () => mockChatChange?.("chat-b", { title: "Other" }));
    await act(async () => mockChatChange?.("chat-a", null));
    expect(result.current.chatTitle).toBeNull();

    await act(async () => mockChatChange?.("chat-a", { title: "Renamed", pinned: true }));
    expect(result.current).toMatchObject({ chatTitle: "Renamed", pinned: true, archived: false });

    mockSession += 1;
    await act(async () => mockChatChange?.("chat-a", { title: "Next account" }));
    expect(result.current.chatTitle).toBe("Renamed");
  });
});
