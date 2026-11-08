import React, { useLayoutEffect } from "react";
import { Alert, Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useChatActions } from "@/features/chat/hooks/useChatActions";
import { exportConversationAsPdf } from "@/features/chat/model/exportMessagePdf";
import { api, type Message } from "@/lib/api";
import { SharingUnavailableError } from "@/lib/shareUnavailable";
import { insertChatGlobal, patchChatGlobal, removeChatGlobal } from "@/features/chat/drawer/drawer";

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 0 }));
jest.mock("@/features/chat/model/chatListCache", () => ({
  getCachedChat: () => ({ id: "chat-1", title: "Old title" }),
  peekCreatedChat: () => undefined,
}));

jest.mock("@/lib/api", () => ({
  api: {
    renameChat: jest.fn(),
    deleteChat: jest.fn(),
    setPin: jest.fn(),
    setArchive: jest.fn(),
    setMessageFeedback: jest.fn(),
    updateMessageEmail: jest.fn(),
    listAllMessages: jest.fn(),
  },
}));

jest.mock("@/features/chat/drawer/drawer", () => ({
  insertChatGlobal: jest.fn(),
  patchChatGlobal: jest.fn(),
  removeChatGlobal: jest.fn(),
}));

jest.mock("@/features/chat/model/messageCache", () => ({
  clearCachedChatMessages: jest.fn(),
  writeCachedChatMessages: jest.fn(async () => undefined),
  patchCachedChatMessage: jest.fn(async () => undefined),
}));

jest.mock("@/features/chat/model/exportMessagePdf", () => ({
  exportConversationAsPdf: jest.fn(),
}));

const mockShare = jest.fn(async (_options: { message: string; title?: string | null }) => {});
jest.mock("@/lib/share", () => ({ presentShareSheet: (options: { message: string; title?: string | null }) => mockShare(options) }));
jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
}));

const mockReportFailure = jest.fn();
jest.mock("@/lib/sentry", () => ({
  ...jest.requireActual("@/lib/sentry"),
  reportFailure: (...args: unknown[]) => mockReportFailure(...args),
}));

const mockFeedbackError = jest.fn();
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => ({ error: mockFeedbackError }),
}));

const setChatTitle = jest.fn();

let actions: ReturnType<typeof useChatActions>;

function Probe() {
  const result = useChatActions({
    token: "tok",
    chatId: "chat-1",
    chatTitle: "Old title",
    messages: [],
    pinned: false,
    setPinned: jest.fn(),
    archived: false,
    setArchived: jest.fn(),
    setChatTitle,
    editThread: jest.fn(),
    t: (key) => key,
  });
  useLayoutEffect(() => { actions = result; });
  return <Text>chat actions</Text>;
}

describe("useChatActions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Alert, "alert").mockImplementation(() => {});
    mockFeedbackError.mockClear();
  });

  it("renames the chat immediately and rolls back on failure", async () => {
    (api.renameChat as jest.Mock).mockRejectedValue(new Error("fail"));
    await act(async () => {
      render(<Probe />);
    });

    await act(async () => {
      actions.setRenameText("New title");
    });
    await act(async () => {
      await actions.confirmRename();
    });

    expect(setChatTitle).toHaveBeenCalledWith("New title");
    expect(patchChatGlobal).toHaveBeenCalledWith("chat-1", { title: "New title" });
    expect(setChatTitle).toHaveBeenCalledWith("Old title");
    expect(patchChatGlobal).toHaveBeenCalledWith("chat-1", { title: "Old title" });
    expect(mockFeedbackError).toHaveBeenCalledWith("chat.rename_failed");
    expect(Alert.alert).not.toHaveBeenCalled();
  });

  it("restores the drawer row when delete fails", async () => {
    (api.deleteChat as jest.Mock).mockRejectedValue(new Error("fail"));
    let deletePress: (() => void | Promise<void>) | undefined;
    (Alert.alert as jest.Mock).mockImplementation((_title, _body, buttons) => {
      const press = (
        buttons as { text: string; onPress?: () => void | Promise<void> }[] | undefined
      )?.find((b) => b.text === "common.delete")?.onPress;
      if (press) deletePress = press;
    });
    await act(async () => {
      render(<Probe />);
    });

    await act(async () => {
      actions.confirmDelete();
    });
    await act(async () => {
      await deletePress?.();
    });

    expect(removeChatGlobal).toHaveBeenCalledWith("chat-1");
    expect(insertChatGlobal).toHaveBeenCalledWith(
      expect.objectContaining({ id: "chat-1", title: "Old title" }),
    );
  });

  it("shares the chat as text straight through the OS share menu from ⋮", async () => {
    // The user wants the share sheet with contacts and apps, not one of Recall's first (2026-11-07).
    (api.listAllMessages as jest.Mock).mockResolvedValueOnce([{ id: "m1", role: "user", content: "hi" }]);
    await act(async () => {
      render(<Probe />);
    });
    await act(async () => {
      actions.setMenuVisible(true);
    });
    await act(async () => {
      actions.onShareFromMenu();
    });

    expect(actions.menuVisible).toBe(false);
    expect(mockShare).toHaveBeenCalledTimes(1);
    expect(mockShare.mock.calls[0][0].message).toContain("hi");
  });

  it("exports the whole chat as a PDF through the module it loads on demand", async () => {
    const full = [{ id: "m1", role: "user", content: "hi" }];
    (api.listAllMessages as jest.Mock).mockResolvedValueOnce(full);
    (exportConversationAsPdf as jest.Mock).mockImplementationOnce(
      async (_title: string, _messages: unknown, onSharing: () => void) => onSharing(),
    );
    await act(async () => {
      render(<Probe />);
    });

    await act(async () => {
      await actions.handleExportPdf();
    });

    expect(exportConversationAsPdf).toHaveBeenCalledWith("Old title", full, expect.any(Function));
    expect(actions.actionBanner).toBeNull();
    expect(mockFeedbackError).not.toHaveBeenCalled();
  });

  it("says it is preparing while the PDF is drawn, until its share sheet opens", async () => {
    (api.listAllMessages as jest.Mock).mockResolvedValueOnce([{ id: "m1", role: "user", content: "hi" }]);
    let share = () => {};
    let finish = () => {};
    (exportConversationAsPdf as jest.Mock).mockImplementationOnce(
      (_title: string, _messages: unknown, onSharing: () => void) =>
        new Promise<void>((resolve) => {
          share = onSharing;
          finish = resolve;
        }),
    );
    await act(async () => {
      render(<Probe />);
    });

    let task: Promise<void> = Promise.resolve();
    await act(async () => {
      task = actions.handleExportPdf();
    });
    expect(actions.actionBanner).not.toBeNull();

    await act(async () => share());
    expect(actions.actionBanner).toBeNull();
    await act(async () => {
      finish();
      await task;
    });
  });

  it("stays quiet when the share sheet is closed, and reports a failed export", async () => {
    (api.listAllMessages as jest.Mock).mockResolvedValue([]);
    const exportPdf = exportConversationAsPdf as jest.Mock;
    exportPdf.mockRejectedValueOnce(new Error("User did not share"));
    await act(async () => {
      render(<Probe />);
    });

    await act(async () => {
      await actions.handleExportPdf();
    });
    expect(mockFeedbackError).not.toHaveBeenCalled();

    exportPdf.mockRejectedValueOnce(new Error("print failed"));
    await act(async () => {
      await actions.handleExportPdf();
    });
    expect(mockFeedbackError).toHaveBeenCalledWith("chat.export_pdf_failed");
  });

  it("says to update the app when this build cannot share the PDF", async () => {
    (api.listAllMessages as jest.Mock).mockResolvedValue([{ id: "m1", role: "user", content: "hi" }]);
    (exportConversationAsPdf as jest.Mock).mockRejectedValueOnce(new SharingUnavailableError());
    await act(async () => {
      render(<Probe />);
    });

    await act(async () => {
      await actions.handleExportPdf();
    });
    expect(mockFeedbackError).toHaveBeenCalledWith("common.share_needs_update");
  });

  it("shares the whole chat, and never the loaded page in its place (CLAR-08)", async () => {
    const full = [{ id: "m1", role: "user", content: "hi" }];
    (api.listAllMessages as jest.Mock).mockResolvedValueOnce(full).mockRejectedValueOnce(new Error("offline"));
    await act(async () => {
      render(<Probe />);
    });

    await expect(actions.loadTranscriptMessages()).resolves.toBe(full);
    await expect(actions.loadTranscriptMessages()).rejects.toThrow("offline");
    expect(api.listAllMessages).toHaveBeenCalledWith("tok", "chat-1");
  });

  it("says the PDF failed when the whole chat cannot be read, and exports nothing", async () => {
    (api.listAllMessages as jest.Mock).mockRejectedValueOnce(new Error("offline"));
    await act(async () => {
      render(<Probe />);
    });

    await act(async () => {
      await actions.handleExportPdf();
    });
    expect(exportConversationAsPdf).not.toHaveBeenCalled();
    expect(mockFeedbackError).toHaveBeenCalledWith("chat.export_pdf_failed");
  });
});

const EMAIL_MESSAGE_ID = "11111111-1111-1111-1111-111111111111";
const EMAIL_CONTENT = "Here.\n```email\nTo: a@b.com\nSubject: Hi\n\nHello\n```\n";

describe("useChatActions email draft", () => {
  it("saves with a queued state updater and serializes overlapping writes", async () => {
    const updaters: React.SetStateAction<Message[]>[] = [];
    const original = { id: EMAIL_MESSAGE_ID, role: "assistant", content: EMAIL_CONTENT } as Message;
    const resolvers: ((message: Message) => void)[] = [];
    (api.updateMessageEmail as jest.Mock).mockReset().mockImplementation(
      () => new Promise<Message>((resolve) => resolvers.push(resolve)),
    );
    function DeferredProbe() {
      const result = useChatActions({
        token: "tok", chatId: "chat-1", chatTitle: "Draft", messages: [original],
        pinned: false, setPinned: jest.fn(), archived: false, setArchived: jest.fn(),
        setChatTitle: jest.fn(), editThread: (update) => { updaters.push(update); },
        t: (key) => key,
      });
      useLayoutEffect(() => { actions = result; });
      return <Text>deferred</Text>;
    }
    await render(<DeferredProbe />);
    const first = actions.handleSaveEmailDraft(EMAIL_MESSAGE_ID, { subject: "First", body: "One" });
    const second = actions.handleSaveEmailDraft(EMAIL_MESSAGE_ID, { subject: "Second", body: "Two" });
    await act(async () => { await Promise.resolve(); });
    expect(api.updateMessageEmail).toHaveBeenCalledTimes(1);
    expect(updaters).toHaveLength(0);
    resolvers[0]({ ...original, content: "First saved" });
    expect(await first).toBe(true);
    await act(async () => { await Promise.resolve(); });
    expect(api.updateMessageEmail).toHaveBeenCalledTimes(2);
    resolvers[1]({ ...original, content: "Second saved" });
    expect(await second).toBe(true);
    let state = [original];
    for (const update of updaters) state = typeof update === "function" ? update(state) : update;
    expect(state[0].content).toBe("Second saved");
  });

  it("rewrites the stored email fence and PATCHes it", async () => {
    let messagesState: Message[] = [
      {
        id: EMAIL_MESSAGE_ID,
        role: "assistant",
        content: EMAIL_CONTENT,
        model: "free-chat",
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    const setMessages = jest.fn((update: React.SetStateAction<Message[]>) => {
      messagesState = typeof update === "function" ? update(messagesState) : update;
    });
    const updatedContent = "Here.\n```email\nTo: a@b.com\nSubject: Bye\n\nHello\n```\n";
    (api.updateMessageEmail as jest.Mock).mockResolvedValue({
      id: EMAIL_MESSAGE_ID,
      role: "assistant",
      content: updatedContent,
      model: "free-chat",
      created_at: "2026-01-01T00:00:00Z",
    });

    function EmailProbe() {
      const result = useChatActions({
        token: "tok",
        chatId: "chat-1",
        chatTitle: "Old title",
        messages: messagesState,
        pinned: false,
        setPinned: jest.fn(),
        archived: false,
        setArchived: jest.fn(),
        setChatTitle: jest.fn(),
        editThread: setMessages,
            t: (key) => key,
      });
      useLayoutEffect(() => { actions = result; });
      return <Text>email actions</Text>;
    }

    await act(async () => {
      render(<EmailProbe />);
    });
    await act(async () => {
      await actions.handleSaveEmailDraft(EMAIL_MESSAGE_ID, {
        to: "a@b.com",
        subject: "Bye",
        body: "Hello",
      });
    });

    expect(api.updateMessageEmail).toHaveBeenCalledWith("tok", "chat-1", EMAIL_MESSAGE_ID, {
      to: "a@b.com",
      subject: "Bye",
      body: "Hello",
    });
    expect(messagesState[0]?.content).toContain("Subject: Bye");
  });
});

describe("useChatActions thumbs", () => {
  beforeEach(() => jest.clearAllMocks());

  const REPLY_ID = "22222222-2222-2222-2222-222222222222";
  let thread: Message[] = [];
  const editThread = jest.fn((update: React.SetStateAction<Message[]>) => {
    thread = typeof update === "function" ? update(thread) : update;
  });
  const reply = (id: string): Message => ({ id, role: "assistant", content: "Answer.", model: null, created_at: "t" });
  function ThumbsProbe() {
    const result = useChatActions({
      token: "tok", chatId: "chat-1", chatTitle: "Old title", messages: thread, pinned: false,
      setPinned: jest.fn(), archived: false, setArchived: jest.fn(), setChatTitle: jest.fn(), editThread,
      t: (key) => key,
    });
    useLayoutEffect(() => { actions = result; });
    return <Text>thumbs</Text>;
  }

  it("says a rating did not save and takes it back", async () => {
    thread = [reply(REPLY_ID)];
    const failure = Object.assign(new Error("Request failed: 500"), { status: 500 });
    (api.setMessageFeedback as jest.Mock).mockRejectedValueOnce(failure);
    await act(async () => { render(<ThumbsProbe />); });
    await act(async () => { actions.handleFeedback(REPLY_ID, "up"); });
    expect(thread[0]?.feedback ?? null).toBeNull();
    expect(mockFeedbackError).toHaveBeenCalledWith("chat.feedback_failed");
    expect(mockReportFailure).toHaveBeenCalledWith("message_feedback", failure);
  });

  // A failed earlier tap put back the rating from before it, over the newer tap shown.
  it("keeps a newer tap when an earlier one fails", async () => {
    thread = [reply(REPLY_ID)];
    let failFirst!: (error: Error) => void;
    (api.setMessageFeedback as jest.Mock)
      .mockReturnValueOnce(new Promise((_resolve, reject) => { failFirst = reject; }))
      .mockResolvedValueOnce(reply(REPLY_ID));
    await act(async () => { render(<ThumbsProbe />); });
    await act(async () => { actions.handleFeedback(REPLY_ID, "up"); });
    await act(async () => { actions.handleFeedback(REPLY_ID, "down"); });
    await act(async () => { failFirst(new Error("offline")); });
    expect(thread[0]?.feedback).toBe("down");
  });

  // A reply with no saved id yet (stopped before its id came): the thumb filled and the
  // rating never reached the server, without a word.
  it("does not fill the thumb of a reply the server has not saved, and says so", async () => {
    thread = [reply("streamed-1")];
    await act(async () => { render(<ThumbsProbe />); });
    await act(async () => { actions.handleFeedback("streamed-1", "up"); });
    expect(thread[0]?.feedback ?? null).toBeNull();
    expect(api.setMessageFeedback).not.toHaveBeenCalled();
    expect(mockFeedbackError).toHaveBeenCalledWith("chat.feedback_failed");
  });
});
