import { ApiRequestError } from "@/lib/api/client";
import type { Message } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import React, { useLayoutEffect } from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useChatSend } from "@/features/chat/hooks/useChatSend";
import { pickDocument, uploadChatAttachment } from "@/features/attachments/model/attachments";
import { registerEmailDraftFlusher } from "@/features/drafts/model/emailDraftFlush";
import { notifyWarning, tap } from "@/lib/haptics";
import {
  queryNeedsClientGeo,
  resolveClientGeoForQuery,
} from "@/lib/resolveClientGeoForQuery";
jest.mock("@/lib/auth", () => ({ getSessionGeneration: jest.fn(() => 0) }));
beforeEach(() => { (getSessionGeneration as jest.Mock).mockReturnValue(0); });

const resolveGeo = resolveClientGeoForQuery as jest.Mock;
const needsGeo = queryNeedsClientGeo as jest.Mock;
const uploadAttachment = uploadChatAttachment as jest.Mock;

const inputRef = { current: "hello" };
const mockSetInput = jest.fn();
const mockSetParams = jest.fn();
const mockSetChatId = jest.fn();
const mockSetChatTitle = jest.fn();
const mockFeedbackError = jest.fn();
const mockSwitchThread = jest.fn();
const mockAdoptComposerThread = jest.fn();
const mockStashFailedDraftForThread = jest.fn();
let mockThreadKey = "new";
const mockResetForNewSession = jest.fn();
jest.mock("@/contexts/ComposerDraftContext", () => ({
  useComposerDraftApi: () => ({
    setInput: mockSetInput,
    inputRef,
    switchThread: mockSwitchThread,
    adoptComposerThread: mockAdoptComposerThread,
    stashFailedDraftForThread: mockStashFailedDraftForThread,
    resetForNewSession: mockResetForNewSession,
    getThreadKey: () => mockThreadKey,
  }),
}));
jest.mock("@/contexts/ActionFeedbackContext", () => ({
  useActionFeedbackOptional: () => ({ error: mockFeedbackError }),
}));
jest.mock("expo-router", () => ({
  useRouter: () => ({ setParams: jest.fn() }),
}));
jest.mock("@/features/attachments/model/attachments", () => ({
  pickDocument: jest.fn(),
  pickFromCamera: jest.fn(),
  pickFromPhotoLibrary: jest.fn(),
  uploadChatAttachment: jest.fn(),
  messageTextForSend: jest.fn((text: string) => text),
  HeicUnsupportedError: class extends Error {},
  NativePickerBusyError: class extends Error {},
  NativePickerTimeoutError: class extends Error {},
  PhotoLibraryPermissionError: class extends Error {
    needsSettings = false;
  },
}));
const mockReadScan = jest.fn();
const mockImageIntent = jest.fn();
jest.mock("@/lib/api", () => ({
  api: {
    readScan: (...args: unknown[]) => mockReadScan(...args),
    imageIntent: (...args: unknown[]) => mockImageIntent(...args),
  },
}));
jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  notifyWarning: jest.fn(),
}));
const mockTap = tap as jest.Mock;
const mockNotifyWarning = notifyWarning as jest.Mock;
jest.mock("@/lib/resolveClientGeoForQuery", () => ({
  queryNeedsClientGeo: jest.fn(() => false),
  resolveClientGeoForQuery: jest.fn(async () => ({ ok: true, clientGeo: null })),
}));
jest.mock("@/lib/scheduleIdle", () => ({
  scheduleIdlePromise: () => Promise.resolve(),
}));
jest.mock("@/features/attachments/model/pendingComposerAttachment", () => ({
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
  streaming = false,
  onStreamBusy,
  messages = [],
  imageGenerating,
  onBeforeSend,
  draft,
}: {
  offline?: boolean;
  chatLoading?: boolean;
  chatId?: string | null;
  routeChatId?: string;
  token?: string | null;
  sendMessage?: jest.Mock;
  prepareDraftChat?: jest.Mock;
  setMessages?: jest.Mock;
  streaming?: boolean;
  onStreamBusy?: jest.Mock;
  messages?: Message[];
  imageGenerating?: boolean;
  onBeforeSend?: jest.Mock;
  draft?: Record<string, unknown>;
}) {
  const result = useChatSend({
    token,
    chatId,
    chatLoading,
    routeChatId,
    setChatId: mockSetChatId,
    setChatTitle: mockSetChatTitle,
    router: { setParams: mockSetParams } as never,
    draft: (draft ?? {
      draftChatIdRef: { current: null },
      skipLoadForChatIdRef: { current: null },
      creatingRef: { current: false },
      prepareDraftChat,
      setDraftChatId: jest.fn(),
      discardEmptyChat: jest.fn(),
    }) as never,
    scroll: { newMessageCountRef: { current: 0 } } as never,
    streaming,
    sendMessage,
    setMessages,
    messages,
    selectedModel: "free-chat",
    updateUser: jest.fn(),
    t: (key) => key,
    onStreamBusy,
    isOffline: offline,
    onOfflineBlocked,
    onBeforeSend,
    onGenerateImage,
    imageGenerating,
  });
  useLayoutEffect(() => { current = result; });
  return <Text>send</Text>;
}

describe("useChatSend", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    inputRef.current = "hello";
    mockThreadKey = "new";
    needsGeo.mockReturnValue(false);
    resolveGeo.mockResolvedValue({ ok: true, clientGeo: null });
    mockImageIntent.mockResolvedValue({ subject: null });
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
    expect(mockImageIntent).toHaveBeenCalledWith("token", "Generate an image of a lighthouse");
    expect(onGenerateImage).toHaveBeenCalledWith(
      "a lighthouse",
      "Generate an image of a lighthouse",
      undefined,
      expect.objectContaining({
        ready: expect.any(Promise),
        onFailure: expect.any(Function),
      }),
    );
  });

  it.each([
    ["draw ethanol", "chemistry"],
    ["A lens has focal length 15 cm. Where's the image?", "physics"],
  ])("leaves %j to its subject as chat, not generation", async (text, subject) => {
    inputRef.current = text;
    mockImageIntent.mockResolvedValue({ subject });
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    });
    await act(async () => {
      await current.handleSend();
    });
    expect(mockImageIntent).toHaveBeenCalledWith("token", text);
    expect(onGenerateImage).not.toHaveBeenCalled();
    expect(sendMessage).toHaveBeenCalledWith(text, expect.anything());
    expect(current.sendPhase).toBe("idle");
  });

  it("generates as before when the server cannot say whose turn it is", async () => {
    inputRef.current = "draw me a cat";
    mockImageIntent.mockRejectedValue(new Error("offline"));
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    });
    await act(async () => {
      await current.handleSend();
    });
    expect(onGenerateImage).toHaveBeenCalledWith(
      "cat",
      "draw me a cat",
      undefined,
      expect.anything(),
    );
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("asks the server only about turns the phone would draw", async () => {
    inputRef.current = "hello";
    await act(async () => {
      render(<Probe chatId="chat-1" />);
    });
    await act(async () => {
      await current.handleSend();
    });
    expect(mockImageIntent).not.toHaveBeenCalled();
  });

  it("neither draws nor sends when the chat changes during the check", async () => {
    mockThreadKey = "chat-1";
    inputRef.current = "draw ethanol";
    let answer!: (value: { subject: string | null }) => void;
    mockImageIntent.mockReturnValue(new Promise((resolve) => { answer = resolve; }));
    const sendMessage = jest.fn();
    const view = await render(
      <Probe chatId="chat-1" routeChatId="chat-1" sendMessage={sendMessage} />,
    );
    let sending!: Promise<void>;
    await act(async () => {
      sending = current.handleSend();
      await Promise.resolve();
    });
    expect(current.sendPhase).toBe("preparing");
    mockThreadKey = "chat-2";
    await view.rerender(<Probe chatId="chat-2" routeChatId="chat-2" sendMessage={sendMessage} />);
    await act(async () => {
      answer({ subject: "chemistry" });
      await sending;
    });
    expect(onGenerateImage).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
    expect(mockSetInput).not.toHaveBeenCalledWith("");
    expect(current.sendPhase).toBe("idle");
  });

  it("clears image requests before the email draft flush settles", async () => {
    inputRef.current = "Generate an image of a lighthouse";
    let finishFlush!: (saved: boolean) => void;
    const unregisterFlush = registerEmailDraftFlusher(
      () => new Promise((resolve) => { finishFlush = resolve; }),
    );
    try {
      await render(<Probe />);
      await act(async () => {
        await current.handleSend();
      });

      expect(mockSetInput).toHaveBeenCalledWith("");
      expect(onGenerateImage).toHaveBeenCalledTimes(1);
      const persistence = onGenerateImage.mock.calls[0][3];
      expect(persistence.ready).toBeInstanceOf(Promise);

      await act(async () => {
        finishFlush(true);
        await expect(persistence.ready).resolves.toBe(true);
      });
    } finally {
      unregisterFlush();
    }
  });

  it("restores an image request when the email draft flush fails", async () => {
    inputRef.current = "Generate an image of a lighthouse";
    const unregisterFlush = registerEmailDraftFlusher(
      () => Promise.resolve(false),
    );
    try {
      await render(<Probe />);
      await act(async () => {
        await current.handleSend();
      });

      const persistence = onGenerateImage.mock.calls[0][3];
      await expect(persistence.ready).resolves.toBe(false);
      await act(async () => {
        persistence.onFailure();
      });
      expect(mockSetInput).toHaveBeenLastCalledWith(
        "Generate an image of a lighthouse",
      );
    } finally {
      unregisterFlush();
    }
  });

  it("routes reference-photo lookup phrasing to a normal send, not generation", async () => {
    inputRef.current = "show me an ear";
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    });
    await act(async () => {
      await current.handleSend();
    });
    expect(onGenerateImage).not.toHaveBeenCalled();
    expect(sendMessage).toHaveBeenCalledWith("show me an ear", expect.anything());
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

  it("wipes composer drafts when the account session changes", async () => {
    const view = await act(async () => render(<Probe />));
    expect(mockResetForNewSession).not.toHaveBeenCalled();
    (getSessionGeneration as jest.Mock).mockReturnValue(1);
    await act(async () => {
      view.rerender(<Probe />);
    });
    expect(mockResetForNewSession).toHaveBeenCalledTimes(1);
    expect(mockSwitchThread).toHaveBeenCalledWith("new");
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

  it("paints the user bubble only after geo resolves", async () => {
    inputRef.current = "coffee near me";
    needsGeo.mockReturnValue(true);
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

    // Nothing paints and the draft stays put while the OS permission sheet is
    // up — a deny must never make a just-painted bubble vanish.
    expect(setMessages).not.toHaveBeenCalled();
    expect(mockSetInput).not.toHaveBeenCalledWith("");
    expect(sendMessage).not.toHaveBeenCalled();
    expect(current.sendPhase).toBe("locating");

    await act(async () => {
      finishGeo({ ok: true, clientGeo: null });
      await sendPromise;
    });

    const appended = setMessages.mock.calls[0][0]([{ id: "prior", role: "assistant" }]);
    expect(appended.at(-1)).toMatchObject({ role: "user", content: "coffee near me" });
    expect(sendMessage).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ skipUserBubble: true }),
    );
    expect(current.pendingOutboundId).toBeNull();
    expect(current.sendPhase).toBe("idle");
  });

  it("leaves the draft untouched when geo is cancelled", async () => {
    inputRef.current = "coffee near me";
    needsGeo.mockReturnValue(true);
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
    // No bubble was painted and the composer was never cleared — nothing to
    // roll back; the draft simply never left the composer.
    expect(setMessages).not.toHaveBeenCalled();
    expect(mockSetInput).not.toHaveBeenCalledWith("");
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

    // Geo resolves before the optimistic insert now, so the composer was never
    // cleared — chat-1's draft is still intact and no stash is needed.
    expect(mockStashFailedDraftForThread).not.toHaveBeenCalled();
    expect(mockSetInput).not.toHaveBeenCalledWith("hello");
    expect(current.sendPhase).toBe("idle");
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
    // The draft was never consumed (geo gates the optimistic insert), so it
    // stays on chat-1's composer — no stash/restore dance.
    expect(mockStashFailedDraftForThread).not.toHaveBeenCalled();
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

it("retains the uploaded id when the draft flush fails after the upload", async () => {
  uploadAttachment.mockResolvedValueOnce("uploaded-id");
  const unregisterFlush = registerEmailDraftFlusher(() => Promise.resolve(false));
  try {
    await render(<Probe chatId="chat-1" routeChatId="chat-1" />);
    await act(async () => {
      current.setPendingAttachment({ localUri: "file://report.pdf", contentType: "application/pdf", fileName: "report.pdf", kind: "file" });
    });
    inputRef.current = "hello";
    await act(async () => { await current.handleSend(); });
    expect(current.pendingAttachment?.existingAttachmentId).toBe("uploaded-id");
  } finally {
    unregisterFlush();
  }
});

it("does not upload when geo fails before the optimistic insert", async () => {
  // Top-level its sit outside the describe's clearAllMocks beforeEach — clear
  // the upload mock so the previous test's call doesn't leak in.
  uploadAttachment.mockClear();
  resolveGeo.mockResolvedValueOnce({ ok: false });
  await render(<Probe chatId="chat-1" routeChatId="chat-1" />);
  await act(async () => {
    current.setPendingAttachment({ localUri: "file://report.pdf", contentType: "application/pdf", fileName: "report.pdf", kind: "file" });
  });
  inputRef.current = "hello";
  await act(async () => { await current.handleSend(); });
  // Geo gates the optimistic insert, so the upload never starts and the
  // composer attachment stays put for a retry.
  expect(uploadAttachment).not.toHaveBeenCalled();
  expect(current.pendingAttachment?.localUri).toBe("file://report.pdf");
  expect(current.pendingAttachment?.existingAttachmentId).toBeUndefined();
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

describe("useChatSend math scans", () => {
  const scan = {
    localUri: "file:///crop.jpg",
    contentType: "image/jpeg",
    fileName: "math-scan.jpg",
    kind: "image" as const,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    inputRef.current = "";
    needsGeo.mockReturnValue(false);
    resolveGeo.mockResolvedValue({ ok: true, clientGeo: null });
  });

  async function settle() {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  it("solves a confirmed reading as typed text, with no photo", async () => {
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    });
    await act(async () => {
      current.handleMathScanSolve("x + y = 5\nx - y = 1");
      await settle();
    });
    expect(sendMessage).toHaveBeenCalledWith("Show steps: x + y = 5, x - y = 1", expect.anything());
    expect(uploadAttachment).not.toHaveBeenCalled();
    expect(current.mathScannerOpen).toBe(false);
  });

  it.each([
    ["chemistry", "Find the molar mass of H2O"],
    ["physics", "A ball is dropped from 80 m. Find its speed just before it hits the ground."],
  ] as const)("solves a confirmed %s reading as the text alone", async (subject, reading) => {
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    });
    await act(async () => {
      current.handleMathScanSolve(reading, subject);
      await settle();
    });
    expect(sendMessage).toHaveBeenCalledWith(reading, expect.anything());
    expect(uploadAttachment).not.toHaveBeenCalled();
  });

  it("keeps a typed draft after the scan's text", async () => {
    inputRef.current = "please explain";
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    });
    await act(async () => {
      current.handleMathScanSolve("2x = 4");
      await settle();
    });
    expect(sendMessage).toHaveBeenCalledWith("Show steps: 2x = 4\n\nplease explain", expect.anything());
  });

  it("sends the photo with the reading the student checked", async () => {
    uploadAttachment.mockResolvedValue("att-1");
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    });
    await act(async () => {
      current.handleMathScanCaptured(scan, "math", "2x = 4");
      await settle();
    });
    expect(uploadAttachment).toHaveBeenCalled();
    expect(sendMessage).toHaveBeenCalledWith(
      "Solve the math problem in this image step by step.\n\nI read this as: 2x = 4",
      expect.anything(),
    );
  });

  it("sends a physics photo with its checked reading under the physics line", async () => {
    uploadAttachment.mockResolvedValue("att-1");
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    });
    await act(async () => {
      current.handleMathScanCaptured(scan, "physics", "A ball is dropped from 20 m.");
      await settle();
    });
    expect(sendMessage).toHaveBeenCalledWith(
      "Solve the physics problem in this image step by step.\n\nI read this as: A ball is dropped from 20 m.",
      expect.anything(),
    );
  });

  it("sends a chemistry photo with the reading the student checked", async () => {
    uploadAttachment.mockResolvedValue("att-1");
    const sendMessage = jest.fn();
    await act(async () => {
      render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    });
    await act(async () => {
      current.handleMathScanCaptured(scan, "chemistry", "Find the molar mass of H2O");
      await settle();
    });
    expect(uploadAttachment).toHaveBeenCalled();
    expect(sendMessage).toHaveBeenCalledWith(
      "Solve the chemistry problem in this image step by step.\n\nI read this as: Find the molar mass of H2O",
      expect.anything(),
    );
  });

  it("reads a scan through the API and turns a failure into null", async () => {
    await act(async () => {
      render(<Probe chatId="chat-1" />);
    });
    const controller = new AbortController();
    mockReadScan.mockResolvedValueOnce({ reading: "2x = 4", uncertain: false, source: "mathpix" });
    await expect(current.readScan(scan, "math", controller.signal)).resolves.toEqual({
      reading: "2x = 4",
      uncertain: false,
      source: "mathpix",
    });
    expect(mockReadScan).toHaveBeenCalledWith("token", "math", scan, controller.signal);
    await current.readScan(scan, "physics", controller.signal);
    expect(mockReadScan).toHaveBeenLastCalledWith("token", "physics", scan, controller.signal);
    mockReadScan.mockRejectedValueOnce(new Error("offline"));
    await expect(current.readScan(scan, "math", controller.signal)).resolves.toBeNull();
    mockReadScan.mockRejectedValueOnce(
      new ApiRequestError(429, JSON.stringify({ detail: "Too many scans in a row. Try again in a few minutes." })),
    );
    await expect(current.readScan(scan, "math", controller.signal)).resolves.toEqual({
      error: "chat.scan_rate_limit",
    });
    mockReadScan.mockRejectedValueOnce(
      new ApiRequestError(413, JSON.stringify({ detail: "Image too large" })),
    );
    await expect(current.readScan(scan, "math", controller.signal)).resolves.toEqual({
      error: "chat.scan_too_large",
    });
    // Every subject names the same refusals: an oversized chemistry or physics photo too.
    mockReadScan.mockRejectedValueOnce(
      new ApiRequestError(413, JSON.stringify({ detail: "Image too large" })),
    );
    await expect(current.readScan(scan, "chemistry", controller.signal)).resolves.toEqual({
      error: "chat.scan_too_large",
    });
    mockReadScan.mockRejectedValueOnce(
      new ApiRequestError(404, JSON.stringify({ detail: "Not available" })),
    );
    await expect(current.readScan(scan, "physics", controller.signal)).resolves.toEqual({
      error: "chat.scan_unavailable",
    });
    mockReadScan.mockRejectedValueOnce(
      new ApiRequestError(429, JSON.stringify({ detail: "Too many scans in a row. Try again in a few minutes." })),
    );
    await expect(current.readScan(scan, "chemistry", controller.signal)).resolves.toEqual({
      error: "chat.scan_rate_limit",
    });
    mockReadScan.mockRejectedValueOnce(
      new ApiRequestError(404, JSON.stringify({ detail: "Not available" })),
    );
    await expect(current.readScan(scan, "chemistry", controller.signal)).resolves.toEqual({
      error: "chat.scan_unavailable",
    });
    mockReadScan.mockRejectedValueOnce(new Error("offline"));
    await expect(current.readScan(scan, "chemistry", controller.signal)).resolves.toBeNull();
    mockReadScan.mockRejectedValueOnce(
      new ApiRequestError(500, JSON.stringify({ detail: "vision failed" })),
    );
    await expect(current.readScan(scan, "chemistry", controller.signal)).resolves.toBeNull();
  });
});


describe("useChatSend send steps", () => {
  const image = { localUri: "file://pic.jpg", contentType: "image/jpeg", fileName: "pic.jpg", kind: "image" as const };
  const file = { localUri: "file://report.pdf", contentType: "application/pdf", fileName: "report.pdf", kind: "file" as const };
  const lastImage: Message[] = [
    { id: "u1", role: "user", content: "Generate image: black cat", model: null, created_at: "t" },
    { id: "a1", role: "assistant", content: "[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]", model: null, created_at: "t" },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    inputRef.current = "hello";
    mockThreadKey = "chat-1";
    needsGeo.mockReturnValue(false);
    resolveGeo.mockResolvedValue({ ok: true, clientGeo: null });
    mockImageIntent.mockResolvedValue({ subject: null });
  });

  async function send() {
    await act(async () => { await current.handleSend(); });
  }

  it("asks the user to wait while a reply streams, and keeps the draft", async () => {
    const onStreamBusy = jest.fn();
    const sendMessage = jest.fn();
    await render(<Probe chatId="chat-1" streaming onStreamBusy={onStreamBusy} sendMessage={sendMessage} />);
    await send();
    expect(onStreamBusy).toHaveBeenCalledTimes(1);
    expect(mockTap).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
    expect(mockSetInput).not.toHaveBeenCalled();
  });

  it("ignores an empty tap while a reply streams", async () => {
    const onStreamBusy = jest.fn();
    inputRef.current = "   ";
    await render(<Probe chatId="chat-1" streaming onStreamBusy={onStreamBusy} />);
    await send();
    expect(onStreamBusy).not.toHaveBeenCalled();
    expect(mockTap).not.toHaveBeenCalled();
  });

  it("reports offline before the stream-busy guard", async () => {
    const onStreamBusy = jest.fn();
    await render(<Probe chatId="chat-1" offline streaming onStreamBusy={onStreamBusy} />);
    await send();
    expect(mockNotifyWarning).toHaveBeenCalledTimes(1);
    expect(onOfflineBlocked).toHaveBeenCalledTimes(1);
    expect(onStreamBusy).not.toHaveBeenCalled();
    expect(mockTap).not.toHaveBeenCalled();
  });

  it.each([
    ["an empty composer", "  ", "token"],
    ["no session", "hello", null],
  ])("sends nothing with %s", async (_label, text, token) => {
    inputRef.current = text;
    const sendMessage = jest.fn();
    await render(<Probe chatId="chat-1" token={token} sendMessage={sendMessage} />);
    await send();
    expect(mockTap).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("does not send while a new chat is being created", async () => {
    const sendMessage = jest.fn();
    const draft = {
      draftChatIdRef: { current: null }, skipLoadForChatIdRef: { current: null }, creatingRef: { current: true },
      prepareDraftChat: jest.fn(), setDraftChatId: jest.fn(), discardEmptyChat: jest.fn(),
    };
    await render(<Probe chatId="chat-1" draft={draft} sendMessage={sendMessage} />);
    await send();
    expect(mockTap).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("lets onBeforeSend take the turn after the tap", async () => {
    const onBeforeSend = jest.fn(() => true);
    const sendMessage = jest.fn();
    await render(<Probe chatId="chat-1" onBeforeSend={onBeforeSend} sendMessage={sendMessage} />);
    await send();
    expect(mockTap).toHaveBeenCalledTimes(1);
    expect(onBeforeSend).toHaveBeenCalledWith("hello");
    expect(sendMessage).not.toHaveBeenCalled();
    expect(mockSetInput).not.toHaveBeenCalled();
  });

  it("never asks the server about a photo lookup", async () => {
    inputRef.current = "show me an ear";
    await render(<Probe chatId="chat-1" />);
    await send();
    expect(mockImageIntent).not.toHaveBeenCalled();
    expect(onGenerateImage).not.toHaveBeenCalled();
  });

  it("drops a draw request while an image is still generating", async () => {
    inputRef.current = "draw me a cat";
    const sendMessage = jest.fn();
    await render(<Probe chatId="chat-1" imageGenerating sendMessage={sendMessage} />);
    await send();
    expect(mockTap).toHaveBeenCalledTimes(1);
    expect(mockImageIntent).not.toHaveBeenCalled();
    expect(onGenerateImage).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
    expect(mockSetInput).not.toHaveBeenCalled();
    expect(current.sendPhase).toBe("idle");
  });

  it("edits an attached image instead of sending it", async () => {
    inputRef.current = "make it blue";
    const sendMessage = jest.fn();
    await render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    await act(async () => { current.setPendingAttachment(image); });
    await send();
    expect(onGenerateImage).toHaveBeenCalledWith("make it blue", "make it blue", { attachment: image }, expect.anything());
    expect(current.pendingAttachment).toBeNull();
    expect(uploadAttachment).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("sends a draw request with a file attached as chat", async () => {
    inputRef.current = "draw me a cat";
    uploadAttachment.mockResolvedValue("att-1");
    const sendMessage = jest.fn();
    await render(<Probe chatId="chat-1" sendMessage={sendMessage} />);
    await act(async () => { current.setPendingAttachment(file); });
    await send();
    expect(mockImageIntent).not.toHaveBeenCalled();
    expect(onGenerateImage).not.toHaveBeenCalled();
    expect(sendMessage).toHaveBeenCalledWith("draw me a cat", expect.objectContaining({ attachmentIds: ["att-1"] }));
  });

  it("revises the last generated image from its attachment", async () => {
    inputRef.current = "make it blue";
    await render(<Probe chatId="chat-1" messages={lastImage} />);
    await send();
    expect(onGenerateImage).toHaveBeenCalledWith(
      "black cat, blue",
      "make it blue",
      { ids: ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"] },
      expect.anything(),
    );
  });

  it("restores a failed image request on another thread by stashing it", async () => {
    inputRef.current = "draw me a cat";
    await render(<Probe chatId="chat-1" routeChatId="chat-1" />);
    await send();
    const persistence = onGenerateImage.mock.calls[0][3];
    mockThreadKey = "chat-2";
    await act(async () => { persistence.onFailure(); });
    expect(mockStashFailedDraftForThread).toHaveBeenCalledWith("chat-1", "draw me a cat");
  });

  it("refuses to restore a failed image request over a newer draft", async () => {
    inputRef.current = "draw me a cat";
    await render(<Probe chatId="chat-1" routeChatId="chat-1" />);
    await send();
    const persistence = onGenerateImage.mock.calls[0][3];
    inputRef.current = "something newer";
    mockSetInput.mockClear();
    await act(async () => { persistence.onFailure(); });
    expect(mockSetInput).not.toHaveBeenCalled();
    expect(mockFeedbackError).toHaveBeenCalledWith("chat.restore_draft_blocked");
  });

  it("restores a plain send when the email draft flush fails", async () => {
    const setMessages = jest.fn();
    const sendMessage = jest.fn();
    const unregisterFlush = registerEmailDraftFlusher(() => Promise.resolve(false));
    try {
      await render(<Probe chatId="chat-1" setMessages={setMessages} sendMessage={sendMessage} />);
      await send();
    } finally {
      unregisterFlush();
    }
    const rows = setMessages.mock.calls.reduce(
      (prev: Message[], [update]) => (typeof update === "function" ? update(prev) : update),
      [],
    );
    expect(rows).toEqual([]);
    expect(setMessages).toHaveBeenCalledTimes(2);
    expect(mockSetInput).toHaveBeenNthCalledWith(1, "");
    expect(mockSetInput).toHaveBeenLastCalledWith("hello");
    expect(sendMessage).not.toHaveBeenCalled();
    expect(current.pendingOutboundId).toBeNull();
    expect(current.sendPhase).toBe("idle");
  });

  it.each([
    [new Error("upload failed"), "upload failed"],
    ["not an error", "chat.attach_failed"],
  ])("restores the draft and reports a failed upload (%p)", async (error, message) => {
    uploadAttachment.mockRejectedValueOnce(error);
    const setMessages = jest.fn();
    const sendMessage = jest.fn();
    await render(<Probe chatId="chat-1" setMessages={setMessages} sendMessage={sendMessage} />);
    await act(async () => { current.setPendingAttachment(file); });
    await send();
    expect(uploadAttachment).toHaveBeenCalledWith("token", file);
    expect(mockFeedbackError).toHaveBeenCalledWith(message);
    expect(mockSetInput).toHaveBeenLastCalledWith("hello");
    expect(current.pendingAttachment).toEqual(file);
    expect(setMessages).toHaveBeenCalledTimes(2);
    expect(sendMessage).not.toHaveBeenCalled();
    expect(current.sendPhase).toBe("idle");
  });

  it("restores the draft when the server makes no new chat", async () => {
    const prepareDraftChat = jest.fn().mockResolvedValue(null);
    await render(<Probe prepareDraftChat={prepareDraftChat} />);
    await send();
    expect(prepareDraftChat).toHaveBeenCalledWith("free-chat");
    expect(mockFeedbackError).toHaveBeenCalledWith("chat.error_generic");
    expect(mockSetInput).toHaveBeenLastCalledWith("hello");
    expect(mockSetChatId).not.toHaveBeenCalled();
    expect(current.sendPhase).toBe("idle");
  });

  it("makes a new draft chat the open one, then routes to it", async () => {
    const draft = {
      draftChatIdRef: { current: "created-1" as string | null }, skipLoadForChatIdRef: { current: null as string | null },
      creatingRef: { current: false }, prepareDraftChat: jest.fn(), setDraftChatId: jest.fn(), discardEmptyChat: jest.fn(),
    };
    let creatingDuringPrepare: boolean | null = null;
    draft.prepareDraftChat.mockImplementation(async () => {
      creatingDuringPrepare = draft.creatingRef.current;
      return "created-1";
    });
    mockThreadKey = "new";
    await render(<Probe draft={draft} />);
    await send();
    expect(creatingDuringPrepare).toBe(true);
    expect(draft.creatingRef.current).toBe(false);
    expect(draft.skipLoadForChatIdRef.current).toBe("created-1");
    expect(draft.draftChatIdRef.current).toBeNull();
    const order = [mockSetChatTitle, mockSetChatId, draft.setDraftChatId, mockAdoptComposerThread, mockSetParams]
      .map((fn) => fn.mock.invocationCallOrder[0]);
    expect(order).toEqual([...order].sort((a, b) => a - b));
    expect(mockSetChatTitle).toHaveBeenCalledWith(null);
    expect(mockSetChatId).toHaveBeenCalledWith("created-1");
    expect(draft.setDraftChatId).toHaveBeenCalledWith(null);
    expect(mockSetParams).toHaveBeenCalledWith({ chatId: "created-1" });
    expect(current.sendPhase).toBe("creating");
    expect(current.pendingOutboundId).toMatch(/^local-/);
  });

  it("discards a draft chat created for a view the user left", async () => {
    let finishCreate!: (id: string) => void;
    const draft = {
      draftChatIdRef: { current: null as string | null }, skipLoadForChatIdRef: { current: null },
      creatingRef: { current: false }, setDraftChatId: jest.fn(), discardEmptyChat: jest.fn(),
      prepareDraftChat: jest.fn(() => new Promise<string>((resolve) => { finishCreate = resolve; })),
    };
    mockThreadKey = "new";
    const view = await render(<Probe draft={draft} />);
    let sending!: Promise<void>;
    await act(async () => {
      sending = current.handleSend();
      await Promise.resolve();
      await Promise.resolve();
    });
    draft.draftChatIdRef.current = "created-1";
    mockThreadKey = "chat-2";
    await view.rerender(<Probe chatId="chat-2" routeChatId="chat-2" draft={draft} />);
    await act(async () => { finishCreate("created-1"); await sending; });
    expect(draft.draftChatIdRef.current).toBeNull();
    expect(draft.setDraftChatId).toHaveBeenCalledWith(null);
    expect(draft.discardEmptyChat).toHaveBeenCalledWith("created-1");
    expect(mockStashFailedDraftForThread).toHaveBeenCalledWith("new", "hello");
    expect(draft.creatingRef.current).toBe(false);
  });

  it("dispatches the turn with everything the transport needs", async () => {
    const setMessages = jest.fn();
    const sendMessage = jest.fn();
    const clientGeo = { latitude: 1, longitude: 2 };
    inputRef.current = "  coffee near me ";
    needsGeo.mockReturnValue(true);
    resolveGeo.mockResolvedValue({ ok: true, clientGeo });
    await render(<Probe chatId="chat-1" setMessages={setMessages} sendMessage={sendMessage} />);
    await send();
    expect(resolveGeo).toHaveBeenCalledWith("token", "coffee near me", expect.any(Function), expect.any(Function));
    const [bubble] = setMessages.mock.calls[0][0]([]);
    expect(bubble).toMatchObject({ id: expect.stringMatching(/^local-/), role: "user", content: "coffee near me" });
    expect(sendMessage).toHaveBeenCalledWith("coffee near me", {
      text: "coffee near me",
      composerDraft: { text: "  coffee near me ", attachment: null },
      skipUserBubble: true,
      trackSendingMessageId: bubble.id,
      attachmentIds: undefined,
      localImageUri: null,
      localFileUri: null,
      localFileName: null,
      localFileContentType: null,
      clientGeo,
      model: "free-chat",
    });
    expect(mockSetInput).toHaveBeenCalledWith("");
    expect(current.pendingOutboundId).toBeNull();
    expect(current.sendPhase).toBe("idle");
  });

  it("moves from locating to uploading for a geo question with a photo", async () => {
    let finishGeo!: (value: { ok: true; clientGeo: null }) => void;
    let finishUpload!: (id: string) => void;
    needsGeo.mockReturnValue(true);
    resolveGeo.mockReturnValue(new Promise((resolve) => { finishGeo = resolve; }));
    uploadAttachment.mockReturnValue(new Promise((resolve) => { finishUpload = resolve; }));
    inputRef.current = "where is this near me";
    await render(<Probe chatId="chat-1" />);
    await act(async () => { current.setPendingAttachment(image); });
    let sending!: Promise<void>;
    await act(async () => { sending = current.handleSend(); });
    expect(current.sendPhase).toBe("locating");
    expect(current.pendingAttachment).toEqual(image);
    await act(async () => { finishGeo({ ok: true, clientGeo: null }); });
    expect(current.sendPhase).toBe("uploading");
    expect(current.pendingAttachment).toBeNull();
    await act(async () => { finishUpload("att-1"); await sending; });
    expect(current.sendPhase).toBe("idle");
  });
});
