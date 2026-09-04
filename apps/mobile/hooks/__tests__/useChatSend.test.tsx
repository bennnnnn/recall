import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useChatSend } from "@/hooks/useChatSend";
import { uploadChatAttachment } from "@/lib/attachments";
import { resolveClientGeoForQuery } from "@/lib/resolveClientGeoForQuery";

const resolveGeo = resolveClientGeoForQuery as jest.Mock;
const uploadAttachment = uploadChatAttachment as jest.Mock;

const inputRef = { current: "hello" };
const mockSetInput = jest.fn();
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
  scheduleIdlePromise: (callback: () => unknown) => Promise.resolve(callback()),
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
  chatId = null,
  routeChatId,
  sendMessage = jest.fn(),
  prepareDraftChat = jest.fn(),
  setMessages = jest.fn(),
}: {
  offline?: boolean;
  chatId?: string | null;
  routeChatId?: string;
  sendMessage?: jest.Mock;
  prepareDraftChat?: jest.Mock;
  setMessages?: jest.Mock;
}) {
  current = useChatSend({
    token: "token",
    chatId,
    routeChatId,
    setChatId: jest.fn(),
    setChatTitle: jest.fn(),
    router: { setParams: jest.fn() } as never,
    draft: {
      draftChatIdRef: { current: null },
      skipLoadForChatIdRef: { current: null },
      creatingRef: { current: false },
      prepareDraftChat,
      setDraftChatId: jest.fn(),
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
      view.rerender(<Probe chatId="chat-1" routeChatId="chat-2" />);
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
      view.rerender(<Probe chatId="chat-1" routeChatId="chat-2" />);
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
});
