import type React from "react";
import { AccessibilityInfo } from "react-native";
import { act, renderHook } from "@testing-library/react-native";

import type { Message } from "@/lib/api";
import type { ChatSsePayload } from "@/features/chat/model/sse";
import type { StreamingDraft } from "@/lib/streamingDraftStore";
import {
  useChatIncomingEvents,
  type PendingSend,
  type RejectedSend,
} from "@/features/chat/hooks/useChatIncoming";
import { clearPendingChatTtft, markChatFirstToken } from "@/features/chat/model/latency";
import { setConsentRequiredHandler } from "@/lib/api/consentRefusal";

jest.mock("@/features/chat/model/sse", () => ({
  isSseAbortError: (error: Error) => error.name === "AbortError",
}));
jest.mock("@/features/chat/model/latency", () => ({
  clearPendingChatTtft: jest.fn(),
  markChatFirstToken: jest.fn(),
}));
jest.mock("@/lib/api", () => ({ api: { listMessages: jest.fn() } }));

const NOW = Date.parse("2026-03-01T12:00:00Z");

async function setup(start: { messages?: Message[]; streaming?: boolean; draft?: StreamingDraft | null } = {}) {
  let messages: Message[] = start.messages ?? [];
  const setMessages = jest.fn((update: React.SetStateAction<Message[]>) => {
    messages = typeof update === "function" ? update(messages) : update;
  });
  const cue = { reset: jest.fn(), activity: jest.fn(), complete: jest.fn(), stopped: jest.fn(), error: jest.fn() };
  const streamingDraftRef = { current: start.draft ?? null };
  const todoSyncTimersRef = { current: [] as ReturnType<typeof setTimeout>[] };
  const args = {
    t: (key: string) => key,
    token: "token",
    chatId: "chat-1",
    isCurrentView: jest.fn(() => true),
    currentSocket: jest.fn(() => null),
    messagesRef: { current: [] as Message[] },
    sendAttemptRef: { current: 1 },
    setMessages,
    setStreaming: jest.fn(),
    setFinalizing: jest.fn(),
    setSendingMessageId: jest.fn(),
    updateStreamingDraft: jest.fn((draft: StreamingDraft | null) => { streamingDraftRef.current = draft; }),
    appendStreamingPlaceholder: jest.fn(),
    queueUnsavedSend: jest.fn(),
    restoreRegenerateBackup: jest.fn(),
    clearStreamingBubble: jest.fn(),
    reportError: jest.fn(),
    clearTodoSyncTimers: jest.fn(() => {
      for (const id of todoSyncTimersRef.current) clearTimeout(id);
      todoSyncTimersRef.current = [];
    }),
    streamingRef: { current: start.streaming ?? true },
    finalizingRef: { current: false },
    streamCueRef: { current: cue },
    wsAuthFallbackRef: { current: { transport: {} as never, retry: jest.fn() } } as never,
    assistantBufferRef: { current: "" },
    streamingDraftRef,
    pendingSendRef: { current: null as PendingSend | null },
    stoppedStreamedIdRef: { current: null as string | null },
    regenerateUiActiveRef: { current: true },
    regenerateBackupRef: { current: null as Message | null },
    ttftTurnIdRef: { current: "turn-1" as string | null },
    firstReplyRef: { current: false },
    onFirstReplyRef: { current: jest.fn() as (() => void) | undefined },
    onTodosSyncRef: { current: jest.fn() as (() => void) | undefined },
    todoSyncTimersRef,
    viewingChatIdRef: { current: "chat-1" as string | null },
    rejectedSendsRef: { current: new Map<string, RejectedSend[]>() },
  };
  const { result } = await renderHook(() => useChatIncomingEvents(args));
  const send = async (payload: ChatSsePayload, ttftTurnId: string | null = "turn-1") => {
    await act(async () => { result.current.handleChatPayloadForChat("chat-1", payload, ttftTurnId); });
  };
  return { args, cue, send, messages: () => messages };
}

const pending = (): PendingSend => ({
  content: "hello",
  options: {},
  messageId: "local-1",
  retryingRejected: false,
  dispatched: true,
});

const streamingBubble: Message = { id: "streaming", role: "assistant", content: "", model: null, created_at: "t" };

describe("useChatIncomingEvents handleChatPayloadForChat", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers({ now: NOW });
    jest.spyOn(AccessibilityInfo, "announceForAccessibility").mockImplementation(() => undefined);
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it("start opens the stream and keeps the local status", async () => {
    const { args, cue, send } = await setup({ streaming: false, draft: { content: "", status: "searching", statusDetail: "cats" } });
    args.assistantBufferRef.current = "stale";
    // A stopped stream ignores its late deltas, start among them.
    await send({ type: "start" });
    expect(args.setStreaming).not.toHaveBeenCalled();
    expect(cue.activity).not.toHaveBeenCalled();

    args.streamingRef.current = true;
    await send({ type: "start" });
    expect(cue.activity).toHaveBeenCalledTimes(1);
    expect(args.wsAuthFallbackRef.current).toBeNull();
    expect(args.setSendingMessageId).toHaveBeenCalledWith(null);
    expect(args.setFinalizing).toHaveBeenCalledWith(false);
    expect(args.setStreaming).toHaveBeenCalledWith(true);
    expect(args.assistantBufferRef.current).toBe("");
    expect(args.updateStreamingDraft).toHaveBeenCalledWith({ content: "", status: "searching", statusDetail: "cats" });
    expect(args.appendStreamingPlaceholder).toHaveBeenCalledTimes(1);
  });

  it("status shows the phase and its detail, and needs a string phase", async () => {
    const { args, cue, send } = await setup({ draft: { content: "", search_sources: [{ title: "a", url: "u", snippet: "s" }] } });
    args.assistantBufferRef.current = "so far";
    await send({ type: "status", phase: "searching", detail: "weather" });
    expect(args.updateStreamingDraft).toHaveBeenLastCalledWith({
      content: "so far",
      search_sources: [{ title: "a", url: "u", snippet: "s" }],
      status: "searching",
      statusDetail: "weather",
      statusStartedAt: NOW,
    });
    await send({ type: "status", phase: "thinking", detail: "" });
    expect(args.updateStreamingDraft).toHaveBeenLastCalledWith(expect.objectContaining({ status: "thinking", statusDetail: undefined }));
    args.updateStreamingDraft.mockClear();
    await send({ type: "status" });
    expect(args.updateStreamingDraft).not.toHaveBeenCalled();
    expect(cue.activity).toHaveBeenCalledTimes(3);
  });

  it("thinking starts when the model was asked, and keeps that start when sent again", async () => {
    const { args, send } = await setup({ draft: { content: "", status: "composing", statusStartedAt: NOW - 50 } });
    await send({ type: "status", phase: "thinking", elapsed_ms: 2300 });
    expect(args.updateStreamingDraft).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "thinking", statusStartedAt: NOW - 2300 }),
    );
    jest.advanceTimersByTime(4000);
    await send({ type: "status", phase: "thinking", elapsed_ms: 100 });
    expect(args.updateStreamingDraft).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "thinking", statusStartedAt: NOW - 2300 }),
    );
  });

  it("token appends to the buffer, clears the status and marks the first token", async () => {
    const { args, cue, send } = await setup({ draft: { content: "", status: "searching" } });
    args.pendingSendRef.current = pending();
    await send({ type: "token", content: "Hel" }, "turn-9");
    await send({ type: "token" });
    await send({ type: "token", content: "lo" });
    expect(args.pendingSendRef.current).toBeNull();
    expect(markChatFirstToken).toHaveBeenNthCalledWith(1, "turn-9", "token");
    expect(args.assistantBufferRef.current).toBe("Hello");
    expect(args.updateStreamingDraft).toHaveBeenLastCalledWith({
      content: "Hello",
      search_sources: undefined,
      status: undefined,
      statusDetail: undefined,
    });
    expect(cue.activity).toHaveBeenCalledTimes(3);
  });

  it("reasoning changes nothing", async () => {
    const { args, cue, send, messages } = await setup({ messages: [streamingBubble] });
    await send({ type: "reasoning", content: "thinking about it" });
    expect(cue.activity).not.toHaveBeenCalled();
    expect(args.updateStreamingDraft).not.toHaveBeenCalled();
    expect(args.setMessages).not.toHaveBeenCalled();
    expect(messages()).toEqual([streamingBubble]);
  });

  it("stream_end starts finalizing and names the resolved model", async () => {
    const { args, cue, send, messages } = await setup({ messages: [streamingBubble] });
    args.pendingSendRef.current = pending();
    await send({ type: "stream_end" });
    expect(args.pendingSendRef.current).toBeNull();
    expect(args.setFinalizing).toHaveBeenCalledWith(true);
    expect(args.setMessages).not.toHaveBeenCalled();
    await send({ type: "stream_end", resolved_model: "smart-chat" });
    expect(messages()[0].model).toBe("smart-chat");
    expect(cue.activity).not.toHaveBeenCalled();
  });

  it("done settles the turn, merges the reply and runs the first-reply callback once", async () => {
    const { args, cue, send, messages } = await setup({
      messages: [streamingBubble],
      draft: { content: "Hello there" },
    });
    args.assistantBufferRef.current = "Hello there";
    args.pendingSendRef.current = pending();
    args.regenerateBackupRef.current = streamingBubble;
    args.finalizingRef.current = true;
    await send({ type: "done", message_id: "m-1", final_content: "Hello there!", resolved_model: "smart-chat" });
    expect(args.pendingSendRef.current).toBeNull();
    expect(args.regenerateUiActiveRef.current).toBe(false);
    expect(args.wsAuthFallbackRef.current).toBeNull();
    expect(args.regenerateBackupRef.current).toBeNull();
    expect(args.ttftTurnIdRef.current).toBeNull();
    expect(args.setSendingMessageId).toHaveBeenCalledWith(null);
    expect(cue.complete).toHaveBeenCalledTimes(1);
    expect(AccessibilityInfo.announceForAccessibility).toHaveBeenCalledWith("chat.reply_ready");
    expect(args.setStreaming).toHaveBeenCalledWith(false);
    expect(args.setFinalizing).toHaveBeenCalledWith(false);
    expect(args.streamingRef.current).toBe(false);
    expect(args.finalizingRef.current).toBe(false);
    expect(args.assistantBufferRef.current).toBe("");
    expect(args.updateStreamingDraft).toHaveBeenLastCalledWith(null);
    expect(messages()).toEqual([
      expect.objectContaining({ id: "m-1", content: "Hello there!", model: "smart-chat" }),
    ]);
    expect(args.onFirstReplyRef.current).toHaveBeenCalledTimes(1);
    expect(args.onTodosSyncRef.current).not.toHaveBeenCalled();
    expect(args.clearTodoSyncTimers).not.toHaveBeenCalled();

    await send({ type: "done", message_id: "m-2", final_content: "again" });
    expect(args.onFirstReplyRef.current).toHaveBeenCalledTimes(1);
  });

  it("done after Stop reconciles the kept bubble without the reply cue", async () => {
    const kept: Message = { id: "streamed-1", role: "assistant", content: "Hel", model: null, created_at: "t" };
    const { args, cue, send, messages } = await setup({ messages: [kept], streaming: false });
    args.stoppedStreamedIdRef.current = "streamed-1";
    await send({ type: "done", message_id: "m-1", final_content: "Hello", completion: "user_stop" });
    expect(args.stoppedStreamedIdRef.current).toBeNull();
    expect(cue.complete).not.toHaveBeenCalled();
    expect(AccessibilityInfo.announceForAccessibility).not.toHaveBeenCalled();
    expect(messages()).toEqual([expect.objectContaining({ id: "m-1", content: "Hello", generationStopped: true })]);
  });

  it("done with a to-do change syncs now and again at 2.5 s and 7 s", async () => {
    const { args, send } = await setup({ messages: [streamingBubble] });
    const sync = jest.fn();
    args.onTodosSyncRef.current = sync;
    const stale = setTimeout(() => sync("stale"), 1_000);
    args.todoSyncTimersRef.current.push(stale);

    await send({ type: "done", message_id: "m-1", final_content: "Added", todos_changed: true });
    expect(sync).toHaveBeenCalledTimes(1);
    expect(args.clearTodoSyncTimers).toHaveBeenCalledTimes(1);
    expect(args.todoSyncTimersRef.current).toHaveLength(2);

    await act(async () => { jest.advanceTimersByTime(2_499); });
    expect(sync).toHaveBeenCalledTimes(1);
    await act(async () => { jest.advanceTimersByTime(1); });
    expect(sync).toHaveBeenCalledTimes(2);
    // The timers read the ref when they fire, so a newer callback wins.
    const later = jest.fn();
    args.onTodosSyncRef.current = later;
    await act(async () => { jest.advanceTimersByTime(4_499); });
    expect(later).not.toHaveBeenCalled();
    await act(async () => { jest.advanceTimersByTime(1); });
    expect(later).toHaveBeenCalledTimes(1);
    expect(sync).not.toHaveBeenCalledWith("stale");
  });

  it("a second to-do change restarts the re-sync waits", async () => {
    const { args, send } = await setup({ messages: [streamingBubble] });
    const sync = jest.fn();
    args.onTodosSyncRef.current = sync;
    await send({ type: "done", message_id: "m-1", final_content: "Added", todos_changed: true });
    await act(async () => { jest.advanceTimersByTime(2_000); });
    await send({ type: "done", message_id: "m-2", final_content: "Moved", todos_changed: true });
    expect(sync).toHaveBeenCalledTimes(2);
    await act(async () => { jest.advanceTimersByTime(2_499); });
    expect(sync).toHaveBeenCalledTimes(2);
    await act(async () => { jest.advanceTimersByTime(1); });
    expect(sync).toHaveBeenCalledTimes(3);
    await act(async () => { jest.advanceTimersByTime(10_000); });
    expect(sync).toHaveBeenCalledTimes(4);
  });

  it("related_prompts attaches follow-ups to their message only", async () => {
    const reply: Message = { id: "m-1", role: "assistant", content: "Hi", model: null, created_at: "t" };
    const { args, send, messages } = await setup({ messages: [reply], streaming: false });
    await send({ type: "related_prompts", message_id: "m-1", prompts: ["One?", " ", 3, "Two?", "Three?", "Four?"] });
    expect(messages()[0].related_prompts).toEqual(["One?", "Two?", "Three?"]);
    args.setMessages.mockClear();
    await send({ type: "related_prompts", prompts: ["Lost?"] });
    await send({ type: "related_prompts", message_id: "m-1", prompts: [] });
    expect(args.setMessages).not.toHaveBeenCalled();
  });

  it("error on a busy turn queues the unsaved send and reports its reason", async () => {
    const { args, cue, send } = await setup({ messages: [streamingBubble] });
    const turn = pending();
    args.pendingSendRef.current = turn;
    args.queueUnsavedSend.mockImplementation((queued: PendingSend, reason: RejectedSend["reason"]) => {
      args.rejectedSendsRef.current.set("chat-1", [{ ...queued, reason }]);
    });
    await send({ type: "error", code: "busy", message: "Busy" }, null);
    expect(cue.error).toHaveBeenCalledTimes(1);
    expect(args.pendingSendRef.current).toBeNull();
    expect(clearPendingChatTtft).toHaveBeenCalledWith("local-1");
    expect(args.ttftTurnIdRef.current).toBeNull();
    expect(args.queueUnsavedSend).toHaveBeenCalledWith(turn, "send_rejected");
    expect(args.regenerateUiActiveRef.current).toBe(false);
    expect(args.wsAuthFallbackRef.current).toBeNull();
    expect(args.setStreaming).toHaveBeenCalledWith(false);
    expect(args.streamingRef.current).toBe(false);
    expect(args.clearStreamingBubble).toHaveBeenCalledTimes(1);
    expect(args.reportError).toHaveBeenCalledWith("Busy", "send_rejected");
  });

  it("error on a rejected attachment queues it under its own reason", async () => {
    const { args, send } = await setup({ messages: [streamingBubble] });
    args.pendingSendRef.current = pending();
    args.queueUnsavedSend.mockImplementation((queued: PendingSend, reason: RejectedSend["reason"]) => {
      args.rejectedSendsRef.current.set("chat-1", [{ ...queued, reason }]);
    });
    await send({ type: "error", code: "attachment_rejected", message: "Too big" });
    expect(clearPendingChatTtft).toHaveBeenCalledWith("turn-1");
    expect(args.queueUnsavedSend).toHaveBeenCalledWith(expect.anything(), "attachment_rejected");
    expect(args.reportError).toHaveBeenCalledWith("Too big", "attachment_rejected");
  });

  it("start marks the send taken by the server and keeps it for a later error", async () => {
    const { args, send } = await setup({ streaming: true });
    const turn = pending();
    args.pendingSendRef.current = turn;
    await send({ type: "start" });
    expect(args.pendingSendRef.current).toBe(turn);
    expect(turn.accepted).toBe(true);
  });

  it.each([
    // Regression: every code-less error offered Regenerate, which re-answered
    // the previous message when this one was never saved.
    [{ message: "Redis down" }, false, "send_rejected"],
    [{ message: "Too many requests. Try again shortly." }, false, "send_rejected"],
    [{ code: "unavailable", message: "Restarting" }, false, "send_rejected"],
    [{ message: "Failed to save the response. Please retry." }, true, null],
    [{ code: "quota_exceeded", message: "Out of quota" }, false, null],
    [{ code: "model_unavailable", message: "Down" }, false, null],
  ])("error %o with user_message_saved=%s queues a resend: %s", async (frame, saved, reason) => {
    const { args, send } = await setup({ messages: [streamingBubble] });
    const turn = pending();
    args.pendingSendRef.current = turn;
    args.queueUnsavedSend.mockImplementation((queued: PendingSend, why: RejectedSend["reason"]) => {
      args.rejectedSendsRef.current.set("chat-1", [{ ...queued, reason: why }]);
    });
    await send({ type: "error", user_message_saved: saved, ...frame });
    if (reason) {
      expect(args.queueUnsavedSend).toHaveBeenCalledWith(turn, reason);
      expect(args.reportError).toHaveBeenCalledWith(frame.message, reason);
    } else {
      expect(args.queueUnsavedSend).not.toHaveBeenCalled();
      expect(args.reportError).toHaveBeenCalledWith(frame.message, frame.code);
    }
  });

  it("a consent_required error opens the consent screen and keeps the message to resend", async () => {
    const opened = jest.fn();
    setConsentRequiredHandler(opened);
    const { args, send } = await setup({ messages: [streamingBubble] });
    const turn = pending();
    args.pendingSendRef.current = turn;
    await send({ type: "error", code: "consent_required", user_message_saved: false, message: "Agree first" });
    setConsentRequiredHandler(null);
    expect(opened).toHaveBeenCalledTimes(1);
    expect(args.queueUnsavedSend).toHaveBeenCalledWith(turn, "send_rejected");
  });

  it("error keeps a partial reply as a stopped bubble", async () => {
    const { args, send, messages } = await setup({
      messages: [streamingBubble],
      draft: { content: "Half an ans", search_sources: [{ title: "a", url: "u", snippet: "s" }] },
    });
    await send({ type: "error", code: "unavailable" });
    expect(args.queueUnsavedSend).not.toHaveBeenCalled();
    expect(args.updateStreamingDraft).toHaveBeenCalledWith(null);
    expect(messages()).toEqual([expect.objectContaining({
      id: `streamed-${NOW}`,
      content: "Half an ans",
      search_sources: [{ title: "a", url: "u", snippet: "s" }],
      generationStopped: true,
    })]);
    expect(args.stoppedStreamedIdRef.current).toBe(`streamed-${NOW}`);
    expect(args.clearStreamingBubble).not.toHaveBeenCalled();
    expect(args.reportError).toHaveBeenCalledWith("chat.error_generic", "unavailable");
  });

  it("error during a regenerate restores the previous reply", async () => {
    const { args, send } = await setup({ messages: [streamingBubble], draft: { content: "partial" } });
    args.regenerateBackupRef.current = { id: "old", role: "assistant", content: "old", model: null, created_at: "t" };
    await send({ type: "error", message: "Nope" });
    expect(args.restoreRegenerateBackup).toHaveBeenCalledTimes(1);
    expect(args.updateStreamingDraft).not.toHaveBeenCalled();
    expect(args.reportError).toHaveBeenCalledWith("Nope", undefined);
  });

  it("an unknown event type changes nothing", async () => {
    const { args, cue, send } = await setup({ messages: [streamingBubble] });
    for (const type of ["pong", "constructor", "toString", "__proto__"]) await send({ type });
    expect(cue.activity).not.toHaveBeenCalled();
    expect(args.setMessages).not.toHaveBeenCalled();
    expect(args.setStreaming).not.toHaveBeenCalled();
    expect(args.reportError).not.toHaveBeenCalled();
  });

  it("drops frames for another chat or an old view", async () => {
    const { args, send } = await setup({ messages: [streamingBubble] });
    args.viewingChatIdRef.current = "chat-2";
    await send({ type: "start" });
    args.viewingChatIdRef.current = "chat-1";
    args.isCurrentView.mockReturnValue(false);
    await send({ type: "done", message_id: "m-1" });
    expect(args.setStreaming).not.toHaveBeenCalled();
    expect(args.setMessages).not.toHaveBeenCalled();
  });
});
