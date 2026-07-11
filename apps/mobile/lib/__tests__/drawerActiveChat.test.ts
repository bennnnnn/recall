import {
  deletedIncludesActiveChat,
  getActiveChatIdGlobal,
  setActiveChatIdGlobal,
} from "@/lib/drawer";

describe("deletedIncludesActiveChat", () => {
  afterEach(() => {
    setActiveChatIdGlobal(null);
  });

  it("returns false when nothing is open", () => {
    expect(deletedIncludesActiveChat(["a", "b"], null)).toBe(false);
    expect(deletedIncludesActiveChat(["a"])).toBe(false);
  });

  it("returns true when the open chat is in the delete batch", () => {
    expect(deletedIncludesActiveChat(["a", "b"], "b")).toBe(true);
  });

  it("returns false when the open chat was not deleted", () => {
    expect(deletedIncludesActiveChat(["a"], "b")).toBe(false);
  });

  it("reads the registered active chat id by default", () => {
    setActiveChatIdGlobal("open-1");
    expect(getActiveChatIdGlobal()).toBe("open-1");
    expect(deletedIncludesActiveChat(["open-1", "other"])).toBe(true);
    expect(deletedIncludesActiveChat(["other"])).toBe(false);
  });
});
