import React from "react";
import { act, cleanup, render } from "@testing-library/react-native";
import { useChat } from "@/hooks/useChat";
import { streamChatMessageSse } from "@/lib/chatSse";
import { getStreamingDraft, resetStreamingDraftStore } from "@/lib/streamingDraftStore";

jest.mock("react-i18next", () => {
  const t = (key: string) => key;
  return { useTranslation: () => ({ t }) };
});
jest.mock("@/lib/api", () => ({ chatWebSocketUrl: (id: string) => `wss://test/${id}` }));
jest.mock("@/lib/deviceTimezone", () => ({ getDeviceTimezone: () => "UTC" }));
jest.mock("@/lib/chatSse", () => ({
  streamChatMessageSse: jest.fn(),
  streamChatRegenerateSse: jest.fn(),
  shouldAbortPriorSse: (previous: string, next: string) => previous === next,
  isSseAbortError: (error: Error) => error.name === "AbortError",
}));

class FakeSocket {
  static OPEN = 1;
  static instances: FakeSocket[] = [];
  readyState = 0;
  onopen = () => {};
  onclose = () => {};
  onerror = () => {};
  onmessage = (_event: { data: string }) => {};
  send = jest.fn();
  close = jest.fn(() => { this.readyState = 3; });
  constructor(readonly url: string) { FakeSocket.instances.push(this); }
  open() { this.readyState = FakeSocket.OPEN; this.onopen(); }
  emit(payload: object) { this.onmessage({ data: JSON.stringify(payload) }); }
}

let current: ReturnType<typeof useChat>;
const onError = jest.fn();
let mockSessionGeneration = 0;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSessionGeneration }));
function Probe({ chatId, token = "token" }: { chatId: string; token?: string }) {
  const chat = useChat(token, chatId, { onError });
  React.useLayoutEffect(() => { current = chat; });
  return null;
}

async function openSocket() {
  let socket!: FakeSocket;
  await act(async () => {
    const pending = current.connect();
    socket = FakeSocket.instances[FakeSocket.instances.length - 1];
    socket.open();
    await pending;
  });
  return socket;
}

async function sendAndStream(socket: FakeSocket, text = "reply") {
  await act(async () => {
    await current.sendMessage("question");
    socket.emit({ type: "start" });
    socket.emit({ type: "token", content: text });
    jest.advanceTimersByTime(20);
  });
}

describe("useChat transport lifecycle", () => {
  const originalSocket = global.WebSocket;
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    FakeSocket.instances = [];
    mockSessionGeneration = 0;
    global.WebSocket = FakeSocket as unknown as typeof WebSocket;
    resetStreamingDraftStore();
  });
  afterEach(async () => {
    await cleanup();
    jest.clearAllTimers();
    jest.useRealTimers();
    global.WebSocket = originalSocket;
  });

  it("ignores a departed chat's late socket failure while the next chat streams", async () => {
    const view = await render(<Probe chatId="a" />);
    const old = await openSocket();
    await sendAndStream(old, "old reply");
    await view.rerender(<Probe chatId="b" />);
    const active = await openSocket();
    await sendAndStream(active, "current reply");
    await act(async () => { old.onerror(); old.onclose(); });
    expect(current.streaming).toBe(true);
    expect(getStreamingDraft()?.content).toBe("current reply");
    expect(onError).not.toHaveBeenCalled();
  });

  it("never dispatches an old pending send through the next chat's socket", async () => {
    const view = await render(<Probe chatId="a" />);
    let sending!: Promise<void>;
    await act(async () => { sending = current.sendMessage("belongs to a"); });
    const old = FakeSocket.instances[0];
    await view.rerender(<Probe chatId="b" />);
    const active = await openSocket();
    await act(async () => { old.open(); await sending; });
    expect(active.send.mock.calls.map(([data]) => JSON.parse(data))).toEqual([
      { token: "token", client_timezone: "UTC" },
    ]);
    expect(streamChatMessageSse).not.toHaveBeenCalled();
  });

  it("settles connection waiters when the socket closes before opening", async () => {
    await render(<Probe chatId="a" />);
    let settled = false;
    await act(async () => {
      void current.connect().then(() => { settled = true; });
      FakeSocket.instances[0].onclose();
    });
    expect(settled).toBe(true);
  });

  it("does not send a turn stopped during the handshake", async () => {
    await render(<Probe chatId="a" />);
    let sending!: Promise<void>;
    await act(async () => { sending = current.sendMessage("cancel before sending"); });
    const socket = FakeSocket.instances[0];
    await act(async () => { current.stopGeneration(); socket.open(); await sending; });
    expect(socket.send.mock.calls.map(([data]) => JSON.parse(data).type)).not.toContain("message");
    expect(streamChatMessageSse).not.toHaveBeenCalled();
    expect(current.streaming).toBe(false);
  });

  it("preserves partial content on a socket error followed by close", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await sendAndStream(socket, "partial reply");
    await act(async () => { socket.onerror(); socket.onclose(); });
    expect(current.streaming).toBe(false);
    expect(current.messages).toEqual(expect.arrayContaining([
      expect.objectContaining({ content: "partial reply", generationStopped: true }),
    ]));
    expect(current.messages.some((message) => message.id === "streaming")).toBe(false);
  });

  it("ignores a previous view's SSE rejection after navigating away and back", async () => {
    let rejectStream!: (error: Error) => void;
    (streamChatMessageSse as jest.Mock).mockImplementationOnce(() =>
      new Promise<void>((_resolve, reject) => { rejectStream = reject; }),
    );
    const view = await render(<Probe chatId="a" />);
    let sending!: Promise<void>;
    await act(async () => {
      sending = current.sendMessage("old question");
      FakeSocket.instances[0].onerror();
    });
    await view.rerender(<Probe chatId="b" />);
    await view.rerender(<Probe chatId="a" />);
    const active = await openSocket();
    await sendAndStream(active, "new reply");
    await act(async () => { rejectStream(new Error("old request failed")); await sending; });
    expect(current.streaming).toBe(true);
    expect(getStreamingDraft()?.content).toBe("new reply");
    expect(onError).not.toHaveBeenCalled();
  });

  it("does not restart a stopped turn when its server start arrives late", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await act(async () => {
      await current.sendMessage("question");
      current.stopGeneration();
      socket.emit({ type: "start" });
      socket.emit({ type: "token", content: "late" });
    });
    expect(current.streaming).toBe(false);
    expect(current.messages.some((message) => message.id === "streaming")).toBe(false);
  });

  it("isolates a new send from the stopped turn's late done frame", async () => {
    await render(<Probe chatId="a" />);
    const old = await openSocket();
    await sendAndStream(old, "partial old reply");
    await act(async () => { current.stopGeneration(); });
    let sending!: Promise<void>;
    await act(async () => { sending = current.sendMessage("next question"); });
    const next = FakeSocket.instances[1];
    await act(async () => {
      next.open();
      await sending;
      next.emit({ type: "start" });
      next.emit({ type: "token", content: "next reply" });
      old.emit({ type: "done", message_id: "old-id", final_content: "partial old reply" });
      jest.advanceTimersByTime(20);
    });
    expect(current.streaming).toBe(true);
    expect(getStreamingDraft()?.content).toBe("next reply");
  });

  it("restores the old answer when regeneration is stopped before replacement tokens", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await sendAndStream(socket);
    await act(async () => {
      socket.emit({ type: "done", message_id: "saved", final_content: "saved answer" });
    });
    await act(async () => {
      current.beginRegenerateUi();
    });
    await act(async () => { current.stopGeneration(); });
    expect(current.messages).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: "saved", content: "saved answer" }),
    ]));
  });

  it("ignores cancellation from regeneration preparation in a previous view", async () => {
    const view = await render(<Probe chatId="a" />);
    const cancelPrevious = current.cancelRegenerateUi;
    await view.rerender(<Probe chatId="b" />);
    const socket = await openSocket();
    await sendAndStream(socket, "current answer");
    await act(async () => { cancelPrevious(); });
    expect(current.streaming).toBe(true);
    expect(getStreamingDraft()?.content).toBe("current answer");
  });

  it("invalidates regeneration preparation when Stop is pressed", async () => {
    await render(<Probe chatId="a" />);
    let isCurrentAttempt: (() => boolean) | void;
    await act(async () => { isCurrentAttempt = current.beginRegenerateUi(); });
    expect(isCurrentAttempt!()).toBe(true);
    await act(async () => { current.stopGeneration(); });
    expect(isCurrentAttempt!()).toBe(false);
  });

  it("dispatches direct regeneration and preserves its backup before the UI rerenders", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await sendAndStream(socket);
    await act(async () => {
      socket.emit({ type: "done", message_id: "saved", final_content: "original" });
    });
    await act(async () => {
      current.beginRegenerateUi();
      await current.regenerateResponse();
      socket.emit({ type: "error", message: "busy", code: "busy" });
    });
    expect(socket.send.mock.calls.map(([data]) => JSON.parse(data).type)).toContain("regenerate");
    expect(current.messages).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: "saved", content: "original" }),
    ]));
  });

  it("replays an auth-rejected turn through SSE without duplicating the user message", async () => {
    (streamChatMessageSse as jest.Mock).mockImplementationOnce(async ({ onEvent }) => {
      onEvent({ type: "start" });
      onEvent({ type: "token", content: "recovered" });
      onEvent({ type: "done", message_id: "saved", final_content: "recovered" });
    });
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await act(async () => {
      await current.sendMessage("first question");
      socket.emit({ type: "error", message: "Unauthorized" });
      socket.onclose();
    });
    expect(streamChatMessageSse).toHaveBeenCalledWith(expect.objectContaining({
      chatId: "a", content: "first question",
    }));
    expect(current.messages.filter((message) => message.role === "user")).toHaveLength(1);
    expect(current.messages).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: "saved", content: "recovered" }),
    ]));
    expect(onError).not.toHaveBeenCalled();
  });

  it("never replays an already accepted stream after an authentication-like error", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await sendAndStream(socket);
    await act(async () => {
      socket.emit({ type: "error", message: "Unauthorized" });
    });
    expect(streamChatMessageSse).not.toHaveBeenCalled();
    expect(current.streaming).toBe(false);
  });
  it("retries the exact unsaved busy turn after start without regenerating prior history", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await sendAndStream(socket, "previous answer");
    await act(async () => {
      socket.emit({ type: "done", message_id: "previous-answer", final_content: "previous answer" });
      await current.sendMessage("unsaved follow-up", {
        model: "smart-chat", attachmentIds: ["file-id"],
        clientGeo: { label: "Here", latitude: 1, longitude: 2 },
      });
      socket.emit({ type: "start" });
      socket.emit({ type: "error", code: "busy", message: "Still finishing" });
    });
    expect(current.streaming).toBe(false);
    expect(current.messages.map((message) => message.content)).toEqual(["question", "previous answer"]);
    expect(onError).toHaveBeenLastCalledWith("Still finishing", "send_rejected");
    expect(current.rejectedSend?.content).toBe("unsaved follow-up");
    await act(async () => { expect(await current.retryRejectedSend()).toBe(true); });
    const turns = socket.send.mock.calls.map(([data]) => JSON.parse(data)).filter((frame) => frame.type === "message");
    expect(turns).toHaveLength(3);
    expect(turns[2]).toEqual(turns[1]);
    expect(current.messages.filter((message) => message.content === "unsaved follow-up")).toHaveLength(1);
  });

  it("offers exact-message retry for an SSE busy rejection even after start", async () => {
    (streamChatMessageSse as jest.Mock).mockImplementationOnce(async ({ onEvent }) => {
      onEvent({ type: "start" });
      onEvent({ type: "error", code: "busy", message: "Still finishing" });
    });
    await render(<Probe chatId="a" />);
    let pending!: Promise<void>;
    await act(async () => {
      pending = current.sendMessage("SSE follow-up", { attachmentIds: ["a1"], model: "smart-chat" });
      FakeSocket.instances[0].onerror();
      await pending;
    });
    expect(current.messages).toEqual([]);
    expect(current.rejectedSend?.content).toBe("SSE follow-up");
    await act(async () => { await current.retryRejectedSend(); });
    expect(streamChatMessageSse).toHaveBeenLastCalledWith(expect.objectContaining({
      content: "SSE follow-up", attachmentIds: ["a1"], model: "smart-chat",
    }));
  });

  it("does not offer new-send retry for an error that may follow persistence", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await act(async () => {
      await current.sendMessage("possibly saved");
      socket.emit({ type: "start" });
      socket.emit({ type: "error", code: "internal_error", message: "Failed" });
      expect(await current.retryRejectedSend()).toBe(false);
    });
    expect(current.rejectedSend).toBeNull();
    expect(current.messages.some((message) => message.content === "possibly saved")).toBe(true);
  });

  it("keeps a rejected turn on view reopen but blocks stale and cross-account retries", async () => {
    const view = await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await act(async () => {
      await current.sendMessage("belongs to a");
      socket.emit({ type: "error", code: "busy" });
    });
    const retryOldChat = current.retryRejectedSend;
    await view.rerender(<Probe chatId="b" />);
    await act(async () => { expect(await retryOldChat()).toBe(false); });
    expect(current.rejectedSend).toBeNull();
    await view.rerender(<Probe chatId="a" />);
    expect(current.rejectedSend?.content).toBe("belongs to a");
    await act(async () => { expect(await retryOldChat()).toBe(false); });
    mockSessionGeneration++;
    await view.rerender(<Probe chatId="a" token="other-account" />);
    await act(async () => { expect(await current.retryRejectedSend()).toBe(false); });
    expect(current.rejectedSend).toBeNull();
  });

  it("invalidates rejected-send retry on Stop and ignores a later busy frame", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await act(async () => {
      await current.sendMessage("stopped");
      current.stopGeneration();
      socket.emit({ type: "error", code: "busy" });
      expect(await current.retryRejectedSend()).toBe(false);
    });
    expect(current.rejectedSend).toBeNull();
  });

  it("preserves rejected sends through newer successful turns and retries the FIFO without duplicates", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await act(async () => {
      await current.sendMessage("first rejected");
      socket.emit({ type: "error", code: "busy" });
      await current.sendMessage("new successful turn");
      socket.emit({ type: "done", message_id: "saved-new", final_content: "new answer" });
    });
    expect(current.rejectedSend?.content).toBe("first rejected");
    await act(async () => {
      await current.sendMessage("second rejected");
      socket.emit({ type: "error", code: "busy" });
      await current.retryRejectedSend();
      socket.emit({ type: "error", code: "busy" });
    });
    expect(current.rejectedSend?.content).toBe("first rejected");
    await act(async () => {
      await current.retryRejectedSend();
      socket.emit({ type: "done", message_id: "saved-first", final_content: "first answer" });
    });
    expect(current.rejectedSend?.content).toBe("second rejected");
    await act(async () => {
      await current.retryRejectedSend();
      socket.emit({ type: "done", message_id: "saved-second", final_content: "second answer" });
      expect(await current.retryRejectedSend()).toBe(false);
    });
    expect(current.rejectedSend).toBeNull();
    const users = current.messages.filter((message) => message.role === "user");
    expect(users.map((message) => message.content)).toEqual([
      "new successful turn", "first rejected", "second rejected",
    ]);
  });

  it("permits a fresh explicit retry after reopening its conversation", async () => {
    const view = await render(<Probe chatId="a" />);
    const original = await openSocket();
    await act(async () => {
      await current.sendMessage("retained on reopen");
      original.emit({ type: "error", code: "busy" });
    });
    await view.rerender(<Probe chatId="b" />);
    await view.rerender(<Probe chatId="a" />);
    const reopened = await openSocket();
    await act(async () => { expect(await current.retryRejectedSend()).toBe(true); });
    expect(reopened.send).toHaveBeenLastCalledWith(expect.stringContaining('"content":"retained on reopen"'));
  });

  it("clears a queued rejection explicitly on Stop", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await act(async () => {
      await current.sendMessage("discarded retry");
      socket.emit({ type: "error", code: "busy" });
    });
    expect(current.rejectedSend?.content).toBe("discarded retry");
    await act(async () => { current.stopGeneration(); });
    await act(async () => { expect(await current.retryRejectedSend()).toBe(false); });
    expect(current.rejectedSend).toBeNull();
  });

  it("retains uploaded attachment metadata when removing an externally created optimistic bubble", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    const attachmentIds = ["uploaded-id"];
    const clientGeo = { label: "Original location", latitude: 1, longitude: 2 };
    await act(async () => {
      current.setMessages([{
        id: "composer-optimistic", role: "user", content: "attachment question",
        model: null, created_at: new Date().toISOString(),
      }]);
      await current.sendMessage("attachment question", {
        skipUserBubble: true, trackSendingMessageId: "composer-optimistic",
        attachmentIds, clientGeo, localFileUri: "file:///original.pdf",
        localFileName: "original.pdf", localFileContentType: "application/pdf",
      });
      socket.emit({ type: "start" });
      socket.emit({ type: "error", code: "busy" });
    });
    expect(current.messages).toEqual([]);
    attachmentIds[0] = "different-upload";
    clientGeo.label = "Different location";
    await act(async () => { await current.retryRejectedSend(); });
    expect(socket.send).toHaveBeenLastCalledWith(expect.stringContaining('"attachment_ids":["uploaded-id"]'));
    expect(socket.send).toHaveBeenLastCalledWith(expect.stringContaining('"client_location":"Original location"'));
    expect(current.messages.filter((message) => message.role === "user")).toEqual([
      expect.objectContaining({ content: "attachment question", local_file_uri: "file:///original.pdf" }),
    ]);
  });

  it("does not turn an interrupted SSE response into an automatic duplicate send", async () => {
    (streamChatMessageSse as jest.Mock).mockRejectedValueOnce(new Error("EOF before terminal event"));
    await render(<Probe chatId="a" />);
    await act(async () => {
      const pending = current.sendMessage("possibly persisted");
      FakeSocket.instances[0].onerror();
      await pending;
      expect(await current.retryRejectedSend()).toBe(false);
    });
    expect(current.rejectedSend).toBeNull();
    expect(current.messages.some((message) => message.content === "possibly persisted")).toBe(true);
    expect(streamChatMessageSse).toHaveBeenCalledTimes(1);
  });

  it.each(["token", "stream_end"])("never requeues an accepted turn when busy arrives after %s", async (type) => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await act(async () => {
      await current.sendMessage("already accepted");
      socket.emit({ type: "start" });
      socket.emit({ type, content: "partial answer" });
      socket.emit({ type: "error", code: "busy", message: "Another action was rejected" });
      expect(await current.retryRejectedSend()).toBe(false);
    });
    expect(current.rejectedSend).toBeNull();
    expect(current.messages.some((message) => message.content === "already accepted")).toBe(true);
    expect(onError).toHaveBeenLastCalledWith("Another action was rejected", "busy");
  });

  it("retains recovery if navigation prevents a retry from finishing its handshake", async () => {
    const view = await render(<Probe chatId="a" />);
    const original = await openSocket();
    await act(async () => {
      await current.sendMessage("retry not dispatched");
      original.emit({ type: "error", code: "busy" });
    });
    await view.rerender(<Probe chatId="b" />);
    await view.rerender(<Probe chatId="a" />);
    let retrying!: Promise<boolean>;
    await act(async () => { retrying = current.retryRejectedSend(); });
    const waiting = FakeSocket.instances[FakeSocket.instances.length - 1];
    await view.rerender(<Probe chatId="b" />);
    await act(async () => { waiting.open(); expect(await retrying).toBe(false); });
    expect(waiting.send.mock.calls.map(([data]) => JSON.parse(data).type)).not.toContain("message");
    await view.rerender(<Probe chatId="a" />);
    expect(current.rejectedSend?.content).toBe("retry not dispatched");
    const reopened = await openSocket();
    await act(async () => { expect(await current.retryRejectedSend()).toBe(true); });
    expect(reopened.send).toHaveBeenLastCalledWith(expect.stringContaining('"content":"retry not dispatched"'));
    expect(current.messages.filter((message) => message.content === "retry not dispatched")).toHaveLength(1);
  });

  it.each(["ws", "sse"])("recovers a definitely unsaved attachment rejection over %s without resending its invalid id", async (transport) => {
    const originalDraft = { text: "  My exact question\n", attachment: {
      kind: "file" as const, localUri: "file:///original.pdf", fileName: "original.pdf",
      contentType: "application/pdf", existingAttachmentId: "rejected-id",
    } };
    const error = { type: "error", code: "attachment_rejected", message: "File unavailable" };
    (streamChatMessageSse as jest.Mock).mockImplementationOnce(async ({ onEvent }) => {
      onEvent({ type: "start" }); onEvent(error);
    });
    await render(<Probe chatId="a" />);
    const socket = transport === "ws" ? await openSocket() : null;
    await act(async () => {
      const sending = current.sendMessage("My exact question", {
        attachmentIds: ["rejected-id"], composerDraft: originalDraft,
      });
      if (socket) { await sending; socket.emit({ type: "start" }); socket.emit(error); }
      else { FakeSocket.instances[0].onerror(); await sending; }
    });
    expect(current.messages).toEqual([]);
    expect(onError).toHaveBeenLastCalledWith("File unavailable", "attachment_rejected");
    expect(current.rejectedSend?.reason).toBe("attachment_rejected");
    originalDraft.text = "mutated later";
    originalDraft.attachment.localUri = "file:///replacement.pdf";
    await act(async () => { expect(await current.retryRejectedSend()).toBe(false); });
    const restore = jest.fn(() => false);
    await act(async () => { expect(current.restoreRejectedAttachmentDraft(restore)).toBe(false); });
    expect(current.rejectedSend).not.toBeNull();
    expect(restore).toHaveBeenLastCalledWith({ text: "  My exact question\n", attachment: {
      kind: "file", localUri: "file:///original.pdf", fileName: "original.pdf", contentType: "application/pdf",
    } });
    restore.mockReturnValue(true);
    await act(async () => { expect(current.restoreRejectedAttachmentDraft(restore)).toBe(true); });
    expect(current.rejectedSend).toBeNull();
    await act(async () => { expect(current.restoreRejectedAttachmentDraft(restore)).toBe(false); });
    expect(restore).toHaveBeenCalledTimes(2);
    if (socket) expect(socket.send.mock.calls.map(([data]) => JSON.parse(data).type)).toEqual([undefined, "message"]);
    else expect(streamChatMessageSse).toHaveBeenCalledTimes(1);
  });

  it("retains rejected attachment recovery for its chat and refuses stale or cross-account callbacks", async () => {
    const view = await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await act(async () => {
      await current.sendMessage("unsaved file", { attachmentIds: ["bad-id"] });
      socket.emit({ type: "error", code: "attachment_rejected" });
    });
    const oldRestore = current.restoreRejectedAttachmentDraft;
    const restore = jest.fn(() => true);
    await view.rerender(<Probe chatId="b" />);
    await act(async () => { expect(oldRestore(restore)).toBe(false); });
    expect(current.rejectedSend).toBeNull();
    await view.rerender(<Probe chatId="a" />);
    expect(current.rejectedSend?.reason).toBe("attachment_rejected");
    await act(async () => { expect(oldRestore(restore)).toBe(false); });
    const beforeSignout = current.restoreRejectedAttachmentDraft;
    mockSessionGeneration++;
    await act(async () => { expect(beforeSignout(restore)).toBe(false); });
    await view.rerender(<Probe chatId="a" token="other-account" />);
    await act(async () => { expect(current.restoreRejectedAttachmentDraft(restore)).toBe(false); });
    expect(current.rejectedSend).toBeNull();
    expect(restore).not.toHaveBeenCalled();
  });

  it.each(["token", "stream_end", "done"])("never restores an accepted attachment turn after %s", async (type) => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    const restore = jest.fn(() => true);
    await act(async () => {
      await current.sendMessage("already saved", { attachmentIds: ["saved-id"] });
      socket.emit({ type: "start" });
      socket.emit({ type, content: "answer", message_id: "saved", final_content: "answer" });
      socket.emit({ type: "error", code: "attachment_rejected" });
      expect(await current.retryRejectedSend()).toBe(false);
      expect(current.restoreRejectedAttachmentDraft(restore)).toBe(false);
    });
    expect(current.rejectedSend).toBeNull();
    expect(current.messages.some((message) => message.content === "already saved")).toBe(true);
    expect(restore).not.toHaveBeenCalled();
  });

  it("keeps the visible recovery action aligned with mixed rejection reasons in FIFO order", async () => {
    await render(<Probe chatId="a" />);
    const socket = await openSocket();
    await act(async () => {
      await current.sendMessage("busy first");
      socket.emit({ type: "error", code: "busy" });
      await current.sendMessage("attachment second", { attachmentIds: ["bad-id"] });
      socket.emit({ type: "error", code: "attachment_rejected" });
    });
    expect(onError).toHaveBeenLastCalledWith("chat.error_generic", "send_rejected");
    const restore = jest.fn(() => true);
    await act(async () => {
      expect(current.restoreRejectedAttachmentDraft(restore)).toBe(false);
      await current.retryRejectedSend();
      socket.emit({ type: "done", message_id: "first-saved", final_content: "answer" });
    });
    expect(current.rejectedSend?.reason).toBe("attachment_rejected");
    await act(async () => {
      expect(await current.retryRejectedSend()).toBe(false);
      expect(current.restoreRejectedAttachmentDraft(restore)).toBe(true);
    });
    expect(restore).toHaveBeenCalledWith({ text: "attachment second", attachment: null });
    expect(current.rejectedSend).toBeNull();
  });

});
