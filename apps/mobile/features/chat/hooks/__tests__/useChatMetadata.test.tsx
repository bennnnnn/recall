import { act, renderHook } from "@testing-library/react-native";

import { useChatMetadata } from "@/features/chat/hooks/useChatMetadata";
import type { Chat } from "@/lib/api";

let mockSession = 0;
let mockChatChange: ((id: string, patch: Record<string, unknown> | null) => void) | undefined;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
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
