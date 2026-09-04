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
function Probe({ chatId }: { chatId: string }) {
  const chat = useChat("token", chatId, { onError });
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
});
