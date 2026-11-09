import React, { useState } from "react";
import { Text } from "react-native";
import { act, render, waitFor } from "@testing-library/react-native";

import { useChatTitle } from "@/features/chat/hooks/useChatTitle";

let mockSession = 0;
let mockRevision = 0;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));

jest.mock("@/lib/api", () => ({
  api: {
    getChat: jest.fn(),
  },
}));

jest.mock("@/features/chat/model/chatListCache", () => ({
  getCachedChat: jest.fn(),
  noteChatListChanged: jest.fn(),
  peekCreatedChat: jest.fn(),
}));

jest.mock("@/features/chat/drawer/drawer", () => {
  let pending: string | null = null;
  return {
    getChatMutationRevision: () => mockRevision,
    insertChatGlobal: jest.fn(),
    patchChatGlobal: jest.fn(),
    setChatTitleGenerating: jest.fn((id: string | null) => {
      pending = id;
    }),
    isChatTitleGenerating: jest.fn((id: string) => pending === id),
    subscribeChatChanges: jest.fn(),
  };
});

import { api } from "@/lib/api";
import { getCachedChat, noteChatListChanged, peekCreatedChat } from "@/features/chat/model/chatListCache";
import {
  insertChatGlobal,
  patchChatGlobal,
  setChatTitleGenerating,
  subscribeChatChanges,
} from "@/features/chat/drawer/drawer";
import type { Chat } from "@/lib/api";

type ChatChange = (chatId: string, patch: Partial<Chat> | null) => void;
const changeListeners = new Set<ChatChange>();
/** A drawer edit, told as the drawer tells it (`publishChatChange`): the turn's title comes so too. */
function publishChatChange(chatId: string, patch: Partial<Chat> | null): void {
  mockRevision++;
  changeListeners.forEach((listener) => listener(chatId, patch));
}

const getChat = api.getChat as jest.Mock;
const peekCreated = peekCreatedChat as jest.Mock;
const listedChat = getCachedChat as jest.Mock;
const insertChat = insertChatGlobal as jest.Mock;
const patchChat = patchChatGlobal as jest.Mock;
const setGenerating = setChatTitleGenerating as jest.Mock;
const noteListChanged = noteChatListChanged as jest.Mock;
const WAITED = { waitForTitle: true };

const created = {
  id: "chat-a",
  title: null,
  model: "free-chat",
  pinned: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

type TitleHook = ReturnType<typeof useChatTitle>;
let current: TitleHook;
let screenTitle: string | null = null;

function Probe({
  chatId,
  getFirstUserText,
}: {
  chatId: string | null;
  getFirstUserText?: () => string | undefined;
}) {
  const [title, setTitle] = useState<string | null>(null);
  const result = useChatTitle({
    token: "tok",
    chatId,
    setChatTitle: setTitle,
    getFirstUserText,
  });
  React.useLayoutEffect(() => {
    screenTitle = title;
    current = result;
  }, [title, result]);
  return <Text>{title ?? "none"}</Text>;
}

describe("useChatTitle", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    screenTitle = null;
    mockSession = 0;
    mockRevision = 0;
    setGenerating(null);
    peekCreated.mockReturnValue(undefined);
    listedChat.mockReturnValue(undefined);
    getChat.mockResolvedValue({ title: "A's title" });
    changeListeners.clear();
    (subscribeChatChanges as jest.Mock).mockImplementation((listener: ChatChange) => {
      changeListeners.add(listener);
      return () => { changeListeners.delete(listener); };
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  // 2026-11-08 feature test: GET /chats/{id} every 2 s until the topic job's title landed,
  // 47 reads in one run and two for one chat.
  it("reads a new chat at most once for its title, however long the title takes", async () => {
    peekCreated.mockReturnValue(created);
    getChat.mockResolvedValue({ ...created, title: null });
    await render(<Probe chatId="chat-a" />);
    await act(async () => { await current.handleFirstReply(); });
    await act(async () => { jest.advanceTimersByTime(60_000); });
    expect(getChat).toHaveBeenCalledTimes(1);
    expect(getChat).toHaveBeenCalledWith("tok", "chat-a", WAITED);
    // None came in the server's wait: the drawer reads it with the list.
    expect(noteListChanged).toHaveBeenCalledTimes(1);
    expect(setGenerating).toHaveBeenLastCalledWith(null);
  });

  it("does not read again after its one read failed", async () => {
    peekCreated.mockReturnValue(created);
    getChat.mockRejectedValue(new TypeError("Network request failed"));
    await render(<Probe chatId="chat-a" />);
    await act(async () => { await current.handleFirstReply(); });
    await act(async () => { jest.advanceTimersByTime(60_000); });
    expect(getChat).toHaveBeenCalledTimes(1);
    expect(noteListChanged).toHaveBeenCalledTimes(1);
    expect(setGenerating).toHaveBeenLastCalledWith(null);
  });

  it("reads nothing when the title comes on the turn's own stream", async () => {
    peekCreated.mockReturnValue(created);
    await render(<Probe chatId="chat-a" />);
    let pending!: Promise<void>;
    await act(async () => { pending = current.handleFirstReply(undefined, { titleOnStream: true }); });
    expect(insertChat).toHaveBeenCalledWith(created);
    expect(setGenerating).toHaveBeenLastCalledWith("chat-a");
    // The turn's title frame puts it in the drawer, which tells everyone.
    await act(async () => { publishChatChange("chat-a", { title: "Heater repair" }); await pending; });
    await act(async () => { jest.advanceTimersByTime(60_000); });
    expect(getChat).not.toHaveBeenCalled();
    expect(patchChat).not.toHaveBeenCalled();
    expect(noteListChanged).not.toHaveBeenCalled();
    expect(setGenerating).toHaveBeenLastCalledWith(null);
  });

  it("stops waiting for a stream title that never came, and reads none", async () => {
    peekCreated.mockReturnValue(created);
    await render(<Probe chatId="chat-a" />);
    await act(async () => { void current.handleFirstReply(undefined, { titleOnStream: true }); });
    await act(async () => { jest.advanceTimersByTime(12_000); });
    expect(getChat).not.toHaveBeenCalled();
    expect(noteListChanged).toHaveBeenCalledTimes(1);
    expect(setGenerating).toHaveBeenLastCalledWith(null);
  });

  it("does not apply a title from chat A to chat B's header", async () => {
    let resolveGet: (value: { title: string }) => void = () => {};
    getChat.mockImplementation(() => new Promise<{ title: string }>((resolve) => { resolveGet = resolve; }));
    const view = await act(async () => render(<Probe chatId="chat-a" />));
    await act(async () => {
      void current.awaitTitle("tok", "chat-a");
    });
    expect(getChat).toHaveBeenCalledWith("tok", "chat-a", WAITED);

    await act(async () => {
      view.rerender(<Probe chatId="chat-b" />);
    });
    await act(async () => {
      resolveGet({ title: "A's title" });
    });

    expect(screenTitle).toBeNull();
    expect(patchChat).toHaveBeenCalledWith("chat-a", { title: "A's title" });
  });

  it("does not stamp the first user line; asks once for the topic", async () => {
    peekCreated.mockReturnValue(created);
    getChat.mockResolvedValue({ title: "Tonight's leftovers" });

    await act(async () => {
      render(
        <Probe
          chatId="chat-a"
          getFirstUserText={() => "What's still open for me to finish tonight?"}
        />,
      );
    });
    await act(async () => {
      void current.handleFirstReply();
    });

    expect(insertChat).toHaveBeenCalledWith(created);
    await waitFor(() => {
      expect(patchChat).toHaveBeenCalledWith("chat-a", { title: "Tonight's leftovers" });
    });
    expect(getChat).toHaveBeenCalledTimes(1);
    expect(screenTitle).toBe("Tonight's leftovers");
  });

  it("uses Image for an attachment-only first send, then asks once for the topic", async () => {
    peekCreated.mockReturnValue(created);
    let resolveGet!: (value: { title: string }) => void;
    getChat.mockReturnValue(new Promise((resolve) => { resolveGet = resolve; }));

    await act(async () => {
      render(
        <Probe
          chatId="chat-a"
          getFirstUserText={() =>
            "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]"
          }
        />,
      );
    });
    await act(async () => {
      void current.handleFirstReply();
    });

    expect(insertChat).toHaveBeenCalledWith({ ...created, title: "Image" });
    expect(screenTitle).toBe("Image");

    await act(async () => { resolveGet({ title: "Homework photo" }); });
    expect(patchChat).toHaveBeenCalledWith("chat-a", { title: "Homework photo" });
    expect(screenTitle).toBe("Homework photo");
  });

  it("does not read or wait when the drawer row already has a title", async () => {
    listedChat.mockReturnValue({ ...created, title: "Homework" });

    await act(async () => {
      render(<Probe chatId="chat-a" />);
    });
    await act(async () => {
      await current.handleFirstReply();
    });

    expect(getChat).not.toHaveBeenCalled();
    expect(screenTitle).toBe("Homework");

    await act(async () => {
      jest.advanceTimersByTime(10000);
    });
    expect(getChat).not.toHaveBeenCalled();
  });

  it("asks for an explicit chat id before React state has caught up", async () => {
    const fresh = { ...created, id: "chat-new" };
    peekCreated.mockImplementation((id: string) => (id === "chat-new" ? fresh : undefined));
    getChat.mockResolvedValue({ title: "Voice note" });

    await act(async () => {
      render(<Probe chatId={null} />);
    });
    await act(async () => {
      await current.handleFirstReply("chat-new");
    });

    expect(insertChat).toHaveBeenCalledWith(fresh);
    expect(getChat).toHaveBeenCalledWith("tok", "chat-new", WAITED);
    expect(patchChat).toHaveBeenCalledWith("chat-new", { title: "Voice note" });
  });

  it("does not apply a first-reply lookup to a different header", async () => {
    let resolve!: (value: { id: string; title: string }) => void;
    getChat.mockReturnValue(new Promise((done) => { resolve = done; }));
    const view = await render(<Probe chatId="chat-a" />);
    let pending!: Promise<void>;
    await act(async () => { pending = current.handleFirstReply(); });
    await view.rerender(<Probe chatId="chat-b" />);
    await act(async () => {
      resolve({ id: "chat-a", title: "A only" });
      await pending;
    });
    expect(screenTitle).toBeNull();
    expect(insertChat).toHaveBeenCalledWith({ id: "chat-a", title: "A only" });
  });

  it.each(["rename", "logout", "unmount", "return"])('ignores a pending title after %s', async (change) => {
    let resolve!: (value: { title: string }) => void;
    getChat.mockReturnValue(new Promise((done) => { resolve = done; }));
    const view = await render(<Probe chatId="chat-a" />);
    let pending!: Promise<void>;
    await act(async () => { pending = current.awaitTitle("tok", "chat-a"); });
    if (change === "rename") publishChatChange("chat-a", { title: "Mine" });
    if (change === "logout") mockSession++;
    if (change === "unmount") await view.unmount();
    if (change === "return") {
      await view.rerender(<Probe chatId="chat-b" />);
      await view.rerender(<Probe chatId="chat-a" />);
    }
    await act(async () => {
      resolve({ title: "Old title" });
      await pending;
    });
    expect(screenTitle).toBeNull();
    if (change !== "return") expect(patchChat).not.toHaveBeenCalled();
  });

  // Review, 2026-11-07: with no list cached (Delete all dropped it), a pin made while the title
  // was awaited read as a deleted chat, and the new chat's title never arrived.
  it("keeps waiting through a pin made meanwhile, with no list cached", async () => {
    let resolve!: (value: { title: string }) => void;
    getChat.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    await render(<Probe chatId="chat-a" />);
    let pending!: Promise<void>;
    await act(async () => { pending = current.awaitTitle("tok", "chat-a"); });
    publishChatChange("chat-a", { pinned: true });
    await act(async () => { resolve({ title: "A's title" }); await pending; });
    expect(listedChat).not.toHaveBeenCalled();
    expect(patchChat).toHaveBeenCalledWith("chat-a", { title: "A's title" });
    expect(screenTitle).toBe("A's title");
  });

  it("stops waiting for a chat deleted meanwhile, with no list cached", async () => {
    let resolve!: (value: { title: string }) => void;
    getChat.mockReturnValue(new Promise((done) => { resolve = done; }));
    await render(<Probe chatId="chat-a" />);
    let pending!: Promise<void>;
    await act(async () => { pending = current.awaitTitle("tok", "chat-a"); });
    publishChatChange("chat-a", null);
    await act(async () => { await pending; resolve({ title: "A's title" }); });
    expect(patchChat).not.toHaveBeenCalled();
    expect(noteListChanged).not.toHaveBeenCalled();
  });

  it("is not stopped by an edit to another chat", async () => {
    await render(<Probe chatId="chat-a" />);
    let pending!: Promise<void>;
    await act(async () => { pending = current.awaitTitle("tok", "chat-a"); });
    publishChatChange("chat-b", null);
    await act(async () => { await pending; });
    expect(patchChat).toHaveBeenCalledWith("chat-a", { title: "A's title" });
  });

  it("rejects retained title callbacks from an ended account session", async () => {
    const view = await render(<Probe chatId="chat-a" />);
    const stale = current;
    mockSession++;
    await view.rerender(<Probe chatId="chat-b" />);
    setGenerating.mockClear();
    await act(async () => {
      await stale.awaitTitle("tok", "chat-a");
      await stale.handleFirstReply();
    });
    expect(setGenerating).not.toHaveBeenCalled();
    expect(getChat).not.toHaveBeenCalled();
    expect(insertChat).not.toHaveBeenCalled();
  });

  it("drops the answer to its one read after unmount", async () => {
    let resolve!: (value: { title: string }) => void;
    getChat.mockReturnValue(new Promise((done) => { resolve = done; }));
    const view = await render(<Probe chatId="chat-a" />);
    let pending!: Promise<void>;
    await act(async () => { pending = current.awaitTitle("tok", "chat-a"); });
    await view.unmount();
    await act(async () => { resolve({ title: "Late" }); await pending; });
    await act(async () => { jest.advanceTimersByTime(60_000); });
    expect(getChat).toHaveBeenCalledTimes(1);
    expect(patchChat).not.toHaveBeenCalled();
  });

  it("treats a persisted short manual title as finished", async () => {
    listedChat.mockReturnValue({ id: "chat-a", title: "Chat", pinned: false });
    await render(<Probe chatId="chat-a" />);
    await act(async () => { void current.handleFirstReply(); });
    expect(screenTitle).toBe("Chat");
    expect(setGenerating).not.toHaveBeenCalledWith("chat-a");
    await act(async () => { jest.advanceTimersByTime(2000); });
    expect(getChat).not.toHaveBeenCalled();
  });
});
