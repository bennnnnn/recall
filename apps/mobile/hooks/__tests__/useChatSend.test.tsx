import { getSessionGeneration } from "@/lib/auth";
import React, { useLayoutEffect } from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useChatSend } from "@/hooks/useChatSend";
import { pickDocument, uploadChatAttachment } from "@/lib/attachments";
import { resolveClientGeoForQuery } from "@/lib/resolveClientGeoForQuery";
jest.mock("@/lib/auth", () => ({ getSessionGeneration: jest.fn(() => 0) }));
beforeEach(() => { (getSessionGeneration as jest.Mock).mockReturnValue(0); });

const resolveGeo = resolveClientGeoForQuery as jest.Mock;
const uploadAttachment = uploadChatAttachment as jest.Mock;

const inputRef = { current: "hello" };
const mockSetInput = jest.fn();
const mockSetParams = jest.fn();
const mockSetChatId = jest.fn();
const mockFeedbackError = jest.fn();
const mockSwitchThread = jest.fn();
const mockAdoptComposerThread = jest.fn();
const mockStashFailedDraftForThread = jest.fn();
let mockThreadKey = "new";
jest.mock("@/contexts/ComposerDraftContext", () => ({
  useComposerDraftApi: () => ({
    setInput: mockSetInput,
    inputRef,
    switchThread: mockSwitchThread,
    adoptComposerThread: mockAdoptComposerThread,
    stashFailedDraftForThread: mockStashFailedDraftForThread,
    getThreadKey: () => mockThreadKey,
  }),
}));
jest.mock("@/contexts/ActionFeedbackContext", () => ({
  useActionFeedbackOptional: () => ({ error: mockFeedbackError }),
}));
jest.mock("expo-router", () => ({
  useRouter: () => ({ setParams: jest.fn() }),
}));
jest.mock("@/lib/attachments", () => ({
  pickDocument: jest.fn(),
  pickFromCamera: jest.fn(),
  pickFromPhotoLibrary: jest.fn(),
  uploadChatAttachment: jest.fn(),
  messageTextForSend: jest.fn((text: string) => text),
  defaultMathCameraPrompt: "Solve this",
  HeicUnsupportedError: class extends Error {},
}));
jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  notifyWarning: jest.fn(),
}));
jest.mock("@/lib/resolveClientGeoForQuery", () => ({
  resolveClientGeoForQuery: jest.fn(async () => ({ ok: true, clientGeo: null })),
}));
jest.mock("@/lib/scheduleIdle", () => ({
  scheduleIdlePromise: () => Promise.resolve(),
}));
jest.mock("@/lib/pendingComposerAttachment", () => ({
  subscribeComposerAttachmentQueue: () => () => undefined,
  takeQueuedComposerAttachment: () => null,
}));

let current: ReturnType<typeof useChatSend>;
const onOfflineBlocked = jest.fn();
const onGenerateImage = jest.fn();

function Probe({
  offline = false,
  chatLoading = false,
  chatId = null,
  routeChatId,
  token = "token",
  sendMessage = jest.fn(),
  prepareDraftChat = jest.fn(),
  setMessages = jest.fn(),
}: {
  offline?: boolean;
  chatLoading?: boolean;
  chatId?: string | null;
  routeChatId?: string;
  token?: string | null;
  sendMessage?: jest.Mock;
  prepareDraftChat?: jest.Mock;
  setMessages?: jest.Mock;
}) {
  const result = useChatSend({
    token,
    chatId,
    chatLoading,
    routeChatId,
    setChatId: mockSetChatId,
    setChatTitle: jest.fn(),
    router: { setParams: mockSetParams } as never,
    draft: {
      draftChatIdRef: { current: null },
      skipLoadForChatIdRef: { current: null },
      creatingRef: { current: false },
      prepareDraftChat,
      setDraftChatId: jest.fn(),
      discardEmptyChat: jest.fn(),
    } as never,
    scroll: { newMessageCountRef: { current: 0 } } as never,
    streaming: false,
    sendMessage,
    setMessages,
    messages: [],
    selectedModel: "free-chat",
    user: null,
    updateUser: jest.fn(),
    t: (key) => key,
    isOffline: offline,
    onOfflineBlocked,
    onGenerateImage,
  });
  useLayoutEffect(() => { current = result; });
  return <Text>send</Text>;
}

describe("useChatSend", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    inputRef.current = "hello";
    mockThreadKey = "new";
    resolveGeo.mockResolvedValue({ ok: true, clientGeo: null });
  });

  it("keeps the draft and surfaces the offline callback", async () => {
    await act(async () => {
      render(<Probe offline />);
    });
    await act(async () => {
      await current.handleSend();
    });
    expect(onOfflineBlocked).toHaveBeenCalledTimes(1);
  });

  it("routes image intent directly to generation", async () => {
    inputRef.current = "Generate an image of a lighthouse";
    await act(async () => {
      render(<Probe />);
    });
    await act(async () => {
      await current.handleSend();
    });
    expect(onGenerateImage).toHaveBeenCalledWith(
      "a lighthouse",
      "Generate an image of a lighthouse",
    );
  });

  it("blocks duplicate sends while preparation is in flight", async () => {
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    });

    await act(async () => {
      await Promise.all([current.handleSend(), current.handleSend()]);
    });

    expect(sendMessage).toHaveBeenCalledTimes(1);
  });

  it("surfaces new-chat creation failures and restores the draft", async () => {
    const prepareDraftChat = jest.fn().mockRejectedValue(new Error("failed"));
    await act(async () => {
      render(<Probe prepareDraftChat={prepareDraftChat} />);
    });

    await act(async () => {
      await current.handleSend();
    });

    expect(mockSetInput).toHaveBeenCalledWith("hello");
    expect(mockFeedbackError).toHaveBeenCalledWith("chat.error_generic");
    expect(current.sendPhase).toBe("idle");
  });

  it("shows the user bubble before geo resolves", async () => {
    let finishGeo: (value: { ok: true; clientGeo: null }) => void = () => undefined;
    resolveGeo.mockReturnValue(
      new Promise((resolve) => {
        finishGeo = resolve;
      }),
    );
    const setMessages = jest.fn();
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} setMessages={setMessages} />);
    });

    let sendPromise: Promise<void> = Promise.resolve();
    await act(async () => {
      sendPromise = current.handleSend();
      await Promise.resolve();
    });

    expect(setMessages).toHaveBeenCalled();
    const appended = setMessages.mock.calls[0][0]([{ id: "prior", role: "assistant" }]);
    expect(appended.at(-1)).toMatchObject({ role: "user", content: "hello" });
    expect(sendMessage).not.toHaveBeenCalled();
    expect(current.pendingOutboundId).toBeTruthy();
    expect(current.sendPhase).toBe("preparing");

    await act(async () => {
      finishGeo({ ok: true, clientGeo: null });
      await sendPromise;
    });

    expect(sendMessage).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ skipUserBubble: true }),
    );
    expect(current.pendingOutboundId).toBeNull();
    expect(current.sendPhase).toBe("idle");
  });

  it("rolls back the bubble and restores the draft when geo is cancelled", async () => {
    resolveGeo.mockResolvedValue({ ok: false });
    const setMessages = jest.fn((updater) =>
      typeof updater === "function" ? updater([]) : updater,
    );
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} setMessages={setMessages} />);
    });

    await act(async () => {
      await current.handleSend();
    });

    expect(sendMessage).not.toHaveBeenCalled();
    expect(mockSetInput).toHaveBeenCalledWith("hello");
    const addUpdater = setMessages.mock.calls[0][0] as (prev: unknown[]) => unknown[];
    const added = addUpdater([]);
    expect(added).toHaveLength(1);
    const rollback = setMessages.mock.calls.at(-1)?.[0] as (prev: unknown[]) => unknown[];
    expect(rollback(added)).toEqual([]);
    expect(current.sendPhase).toBe("idle");
  });

  it("clears the composer attachment before upload finishes", async () => {
    let finishUpload: (id: string) => void = () => undefined;
    uploadAttachment.mockReturnValue(
      new Promise((resolve) => {
        finishUpload = resolve;
      }),
    );
    inputRef.current = "";
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    });
    await act(async () => {
      current.setPendingAttachment({
        localUri: "file://pic.jpg",
        contentType: "image/jpeg",
        fileName: "pic.jpg",
        kind: "image",
      });
    });

    let sendPromise: Promise<void> = Promise.resolve();
    await act(async () => {
      sendPromise = current.handleSend();
      await Promise.resolve();
    });

    expect(current.pendingAttachment).toBeNull();
    expect(current.sendPhase).toBe("uploading");
    expect(current.attachBusy).toBe(false);
    expect(sendMessage).not.toHaveBeenCalled();

    await act(async () => {
      finishUpload("att-1");
      await sendPromise;
    });
    expect(sendMessage).toHaveBeenCalled();
    expect(current.sendPhase).toBe("idle");
  });

  it("clears attachment when switching threads", async () => {
    const view = await act(async () =>
      render(<Probe chatId="chat-1" routeChatId="chat-1" />),
    );
    await act(async () => {
      current.setPendingAttachment({
        localUri: "file://pic.jpg",
        contentType: "image/jpeg",
        fileName: "pic.jpg",
        kind: "image",
      });
    });
    expect(current.pendingAttachment).not.toBeNull();

    await act(async () => {
      await view.rerender(<Probe chatId="chat-1" routeChatId="chat-2" />);
    });

    expect(current.pendingAttachment).toBeNull();
    expect(mockSwitchThread).toHaveBeenCalledWith("chat-2");
  });

  it("stashes a failed send on the originating thread after a switch", async () => {
    mockThreadKey = "chat-1";
    let finishGeo: (value: { ok: false }) => void = () => undefined;
    resolveGeo.mockReturnValue(
      new Promise((resolve) => {
        finishGeo = resolve;
      }),
    );
    const view = await act(async () =>
      render(<Probe chatId="chat-1" routeChatId="chat-1" />),
    );

    let sendPromise: Promise<void> = Promise.resolve();
    await act(async () => {
      sendPromise = current.handleSend();
      await Promise.resolve();
    });

    mockThreadKey = "chat-2";
    await act(async () => {
      await view.rerender(<Probe chatId="chat-1" routeChatId="chat-2" />);
    });

    await act(async () => {
      finishGeo({ ok: false });
      await sendPromise;
    });

    expect(mockStashFailedDraftForThread).toHaveBeenCalledWith("chat-1", "hello");
    expect(mockSetInput).not.toHaveBeenCalledWith("hello");
  });

  it("does not replace a newer draft when the failed send restores", async () => {
    let finishGeo: (value: { ok: false }) => void = () => undefined;
    resolveGeo.mockReturnValue(
      new Promise((resolve) => {
        finishGeo = resolve;
      }),
    );
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={jest.fn()} />);
    });

    let sendPromise: Promise<void> = Promise.resolve();
    await act(async () => {
      sendPromise = current.handleSend();
      await Promise.resolve();
    });
    inputRef.current = "follow-up";

    await act(async () => {
      finishGeo({ ok: false });
      await sendPromise;
    });

    expect(mockSetInput).not.toHaveBeenCalledWith("hello");
    expect(current.sendPhase).toBe("idle");
  });

  it("adopts the composer onto a newly created chat id", async () => {
    const prepareDraftChat = jest.fn().mockResolvedValue("created-1");
    await act(async () => {
      render(<Probe prepareDraftChat={prepareDraftChat} />);
    });
    await act(async () => {
      await current.handleSend();
    });
    expect(mockAdoptComposerThread).toHaveBeenCalledWith("created-1");
  });

  it("keeps the draft while the requested chat is still loading", async () => {
    const sendMessage = jest.fn();
    await render(<Probe chatId="chat-1" routeChatId="chat-2" sendMessage={sendMessage} />);
    await act(async () => { await current.handleSend(); });
    expect(sendMessage).not.toHaveBeenCalled();
    expect(mockSetInput).not.toHaveBeenCalled();
  });

  it("keeps the draft until history loading finishes", async () => {
    const sendMessage = jest.fn();
    await render(<Probe chatId="chat-1" routeChatId="chat-1" chatLoading sendMessage={sendMessage} />);
    await act(async () => { await current.handleSend(); });
    expect(sendMessage).not.toHaveBeenCalled();
    expect(mockSetInput).not.toHaveBeenCalled();
  });

  it("does not dispatch a prepared send after switching chats", async () => {
    mockThreadKey = "chat-1";
    let finishGeo!: (value: { ok: true; clientGeo: null }) => void;
    resolveGeo.mockReturnValue(new Promise((resolve) => { finishGeo = resolve; }));
    const sendMessage = jest.fn();
    const view = await render(<Probe chatId="chat-1" routeChatId="chat-1" sendMessage={sendMessage} />);
    let sending!: Promise<void>;
    await act(async () => {
      sending = current.handleSend();
      await Promise.resolve();
    });
    mockThreadKey = "chat-2";
    await view.rerender(<Probe chatId="chat-2" routeChatId="chat-2" sendMessage={sendMessage} />);
    await act(async () => {
      finishGeo({ ok: true, clientGeo: null });
      await sending;
    });
    expect(sendMessage).not.toHaveBeenCalled();
    expect(mockStashFailedDraftForThread).toHaveBeenCalledWith("chat-1", "hello");
    expect(current.sendPhase).toBe("idle");
  });

  it("does not reopen a new chat when creation finishes after navigation", async () => {
    let finishCreate!: (id: string) => void;
    const prepareDraftChat = jest.fn(() => new Promise((resolve) => { finishCreate = resolve; }));
    const view = await render(<Probe prepareDraftChat={prepareDraftChat} />);
    let sending!: Promise<void>;
    await act(async () => {
      sending = current.handleSend();
      await Promise.resolve();
      await Promise.resolve();
    });
    mockThreadKey = "chat-2";
    await view.rerender(<Probe chatId="chat-2" routeChatId="chat-2" />);
    await act(async () => {
      finishCreate("created-1");
      await sending;
    });
    expect(mockSetParams).not.toHaveBeenCalled();
    expect(mockAdoptComposerThread).not.toHaveBeenCalled();
    expect(mockSetChatId).not.toHaveBeenCalled();
    expect(current.sendPhase).toBe("idle");
  });


  it("dispatches a new chat's pending send once its own id is loaded", async () => {
    const prepareDraftChat = jest.fn().mockResolvedValue("created-1");
    const sendMessage = jest.fn();
    const view = await render(<Probe prepareDraftChat={prepareDraftChat} sendMessage={sendMessage} />);
    await act(async () => { await current.handleSend(); });
    expect(sendMessage).not.toHaveBeenCalled();
    mockThreadKey = "created-1";
    await view.rerender(<Probe chatId="created-1" routeChatId="created-1" sendMessage={sendMessage} />);
    expect(sendMessage).toHaveBeenCalledTimes(1);
    expect(sendMessage).toHaveBeenCalledWith("hello", expect.objectContaining({ skipUserBubble: true }));
    expect(current.sendPhase).toBe("idle");
  });

});


it("does not move a late picker result into another chat", async () => {
  let finish!: (value: unknown) => void;
  (pickDocument as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = await render(<Probe chatId="chat-1" routeChatId="chat-1" />);
  let picking!: Promise<void>;
  await act(async () => { picking = current.handleAttachmentSheetSelect("file"); });
  await view.rerender(<Probe chatId="chat-2" routeChatId="chat-2" />);
  await act(async () => {
    finish({ localUri: "file://report.pdf", contentType: "application/pdf", fileName: "report.pdf", kind: "file" });
    await picking;
  });
  expect(current.pendingAttachment).toBeNull();
});

it("retains the uploaded id when later send preparation fails", async () => {
  uploadAttachment.mockResolvedValueOnce("uploaded-id");
  resolveGeo.mockResolvedValueOnce({ ok: false });
  await render(<Probe chatId="chat-1" routeChatId="chat-1" />);
  await act(async () => {
    current.setPendingAttachment({ localUri: "file://report.pdf", contentType: "application/pdf", fileName: "report.pdf", kind: "file" });
  });
  inputRef.current = "hello";
  await act(async () => { await current.handleSend(); });
  expect(current.pendingAttachment?.existingAttachmentId).toBe("uploaded-id");
});

it("does not attach a previous account's picker result", async () => {
  let finish!: (value: unknown) => void;
  (pickDocument as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = await render(<Probe chatId="chat-1" routeChatId="chat-1" />);
  let picking!: Promise<void>;
  await act(async () => { picking = current.handleAttachmentSheetSelect("file"); });
  (getSessionGeneration as jest.Mock).mockReturnValue(1);
  await view.rerender(<Probe chatId="chat-1" routeChatId="chat-1" token="other-account" />);
  await act(async () => {
    finish({ localUri: "file://private.pdf", contentType: "application/pdf", fileName: "private.pdf", kind: "file" });
    await picking;
  });
  expect(current.pendingAttachment).toBeNull();
});

it.each(["newer message", ""])("preserves a newer attachment and draft (%s) when an older upload fails", async (newDraft) => {
  let fail!: (error: Error) => void;
  uploadAttachment.mockReturnValueOnce(new Promise((_resolve, reject) => { fail = reject; }));
  const oldAttachment = { localUri: "file://old.pdf", contentType: "application/pdf", fileName: "old.pdf", kind: "file" as const };
  const newAttachment = { ...oldAttachment, localUri: "file://new.pdf", fileName: "new.pdf" };
  await render(<Probe chatId="chat-1" routeChatId="chat-1" />);
  inputRef.current = "older message";
  await act(async () => { current.setPendingAttachment(oldAttachment); });
  let sending!: Promise<void>;
  await act(async () => { sending = current.handleSend(); });
  inputRef.current = newDraft;
  await act(async () => { current.setPendingAttachment(newAttachment); });
  mockSetInput.mockClear();
  await act(async () => { fail(new Error("upload failed")); await sending; });
  expect(inputRef.current).toBe(newDraft);
  expect(mockSetInput).not.toHaveBeenCalled();
  expect(current.pendingAttachment).toEqual(newAttachment);
});

it("does not restore the previous account's failed attachment or text", async () => {
  let fail!: (error: Error) => void;
  uploadAttachment.mockReturnValueOnce(new Promise((_resolve, reject) => { fail = reject; }));
  const view = await render(<Probe chatId="chat-1" routeChatId="chat-1" />);
  await act(async () => {
    current.setPendingAttachment({ localUri: "file://private.pdf", contentType: "application/pdf", fileName: "private.pdf", kind: "file" });
  });
  let sending!: Promise<void>;
  await act(async () => { sending = current.handleSend(); });
  (getSessionGeneration as jest.Mock).mockReturnValue(1);
  await view.rerender(<Probe chatId="chat-1" routeChatId="chat-1" token="other-account" />);
  mockSetInput.mockClear();
  mockStashFailedDraftForThread.mockClear();
  mockFeedbackError.mockClear();
  await act(async () => { fail(new Error("upload failed")); await sending; });
  expect(current.pendingAttachment).toBeNull();
  expect(mockSetInput).not.toHaveBeenCalled();
  expect(mockStashFailedDraftForThread).not.toHaveBeenCalled();
  expect(mockFeedbackError).not.toHaveBeenCalled();
});

it("continues an attachment send through an access-token refresh in the same session", async () => {
  let finish!: (id: string) => void;
  uploadAttachment.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  resolveGeo.mockResolvedValue({ ok: true, clientGeo: null });
  const sendMessage = jest.fn();
  const view = await render(<Probe chatId="chat-1" routeChatId="chat-1" sendMessage={sendMessage} />);
  await act(async () => {
    current.setPendingAttachment({ localUri: "file://report.pdf", contentType: "application/pdf", fileName: "report.pdf", kind: "file" });
  });
  let sending!: Promise<void>;
  await act(async () => { sending = current.handleSend(); });
  await view.rerender(<Probe chatId="chat-1" routeChatId="chat-1" token="refreshed" sendMessage={sendMessage} />);
  await act(async () => { finish("uploaded-id"); await sending; });
  expect(sendMessage).toHaveBeenCalledTimes(1);
  expect(sendMessage).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ attachmentIds: ["uploaded-id"] }));
});


describe("rejected attachment composer recovery", () => {
  const attachment = { kind: "file" as const, localUri: "file:///original.pdf", fileName: "original.pdf", contentType: "application/pdf" };
  beforeEach(() => { jest.clearAllMocks(); inputRef.current = ""; mockThreadKey = "a"; });

  it("restores the exact empty-caption file draft without sending", async () => {
    const sendMessage = jest.fn();
    await render(<Probe chatId="a" routeChatId="a" sendMessage={sendMessage} />);
    await act(async () => { expect(current.restoreComposerDraft({ text: "  ", attachment })).toBe(true); });
    expect(mockSetInput).toHaveBeenCalledWith("  ");
    expect(current.pendingAttachment).toEqual(attachment);
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it.each(["text", "file"])("preserves a newer %s draft and reports why recovery waits", async (newer) => {
    await render(<Probe chatId="a" routeChatId="a" />);
    const replacement = { ...attachment, fileName: "new.pdf", localUri: "file:///new.pdf" };
    if (newer === "text") inputRef.current = "new question";
    else await act(async () => { current.setPendingAttachment(replacement); });
    await act(async () => { expect(current.restoreComposerDraft({ text: "old question", attachment })).toBe(false); });
    expect(mockSetInput).not.toHaveBeenCalled();
    expect(current.pendingAttachment).toEqual(newer === "file" ? replacement : null);
    expect(mockFeedbackError).toHaveBeenCalledWith("chat.restore_draft_blocked");
  });

  it("refuses a restore callback captured before navigation or signout", async () => {
    const view = await render(<Probe chatId="a" routeChatId="a" />);
    const oldRestore = current.restoreComposerDraft;
    await view.rerender(<Probe chatId="b" routeChatId="b" />);
    await act(async () => { expect(oldRestore({ text: "a", attachment })).toBe(false); });
    const beforeSignout = current.restoreComposerDraft;
    (getSessionGeneration as jest.Mock).mockReturnValue(1);
    await act(async () => { expect(beforeSignout({ text: "b", attachment })).toBe(false); });
    expect(mockSetInput).not.toHaveBeenCalled();
  });

  it("retains untrimmed composer text alongside its uploaded attachment for recovery", async () => {
    inputRef.current = "  exact question\n";
    uploadAttachment.mockResolvedValue("uploaded-id");
    const sendMessage = jest.fn();
    await render(<Probe chatId="a" routeChatId="a" sendMessage={sendMessage} />);
    await act(async () => { current.setPendingAttachment(attachment); });
    await act(async () => { await current.handleSend(); });
    expect(sendMessage).toHaveBeenCalledWith("exact question", expect.objectContaining({ composerDraft: {
      text: "  exact question\n", attachment: { ...attachment, existingAttachmentId: "uploaded-id" },
    } }));
  });
});
