import {
  archiveBulkTargets,
  chatsFromSelection,
  clearChatSelection,
  selectAllChatIds,
  toggleChatSelection,
} from "@/lib/drawerChatSelection";
import { emptyChatList } from "@/lib/drawerChatList";
import type { Chat } from "@/lib/api";

function chat(id: string, patch: Partial<Chat> = {}): Chat {
  return {
    id,
    title: null,
    model: "free-chat",
    pinned: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...patch,
  };
}

describe("drawerChatSelection", () => {
  it("toggles ids in a set copy", () => {
    expect([...toggleChatSelection(new Set(["a"]), "a")]).toEqual([]);
    expect([...toggleChatSelection(new Set(), "b")]).toEqual(["b"]);
  });

  it("selects all chat ids and clears", () => {
    expect([...selectAllChatIds([chat("a"), chat("b")])]).toEqual(["a", "b"]);
    expect(clearChatSelection().size).toBe(0);
  });

  it("resolves selected chats from groups", () => {
    const groups = {
      ...emptyChatList(),
      today: [chat("a"), chat("b")],
      archived: [chat("z", { archived: true })],
    };
    const selected = new Set(["a", "z"]);
    expect(chatsFromSelection(groups, selected).map((c) => c.id)).toEqual(["a", "z"]);
  });

  it("filters archive targets to non-archived chats", () => {
    const targets = archiveBulkTargets([
      chat("a"),
      chat("b", { archived: true }),
    ]);
    expect(targets.map((c) => c.id)).toEqual(["a"]);
  });
});
