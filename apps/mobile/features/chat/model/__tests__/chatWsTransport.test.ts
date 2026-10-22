import { createWsBackoff, WS_RETRY_BASE_MS, WS_RETRY_MAX_MS } from "@/features/chat/model/wsBackoff";
import {
  WS_ACK_PROBE_MS,
  WS_CONNECT_TIMEOUT_MS,
  WS_FIRST_EVENT_TIMEOUT_MS,
  WS_FOLLOW_UPS_WAIT_MS,
  WS_PROBE_TIMEOUT_MS,
} from "@/features/chat/model/wsConnect";
import {
  ChatWsTransport,
  type ChatWsFallbackSignal,
} from "@/features/chat/model/wsTransport";

class FakeSocket {
  readyState = 0;
  onopen: () => void = () => {};
  onclose: () => void = () => {};
  onerror: () => void = () => {};
  onmessage: (event: { data: string }) => void = () => {};
  readonly send = jest.fn();
  readonly close = jest.fn(() => {
    this.readyState = 3;
  });

  open(): void {
    this.readyState = 1;
    this.onopen();
  }

  emit(payload: object): void {
    this.onmessage({ data: JSON.stringify(payload) });
  }
}

function setupTransport() {
  // The first socket is ready before connect(); each later connect gets a new one.
  const socket = new FakeSocket();
  const sockets = [socket];
  let handedOut = 0;
  const onPayload = jest.fn();
  const onFallback = jest.fn<void, [ChatWsFallbackSignal]>();
  const transport = new ChatWsTransport({
    url: "wss://test/chat",
    token: "token",
    clientTimezone: "UTC",
    onPayload,
    onFallback,
    backoff: createWsBackoff(),
    createSocket: () => {
      if (handedOut > 0) sockets.push(new FakeSocket());
      return sockets[handedOut++] as unknown as WebSocket;
    },
  });
  return { socket, sockets, transport, onPayload, onFallback };
}

const MESSAGE = {
  content: "hello",
  attachment_ids: [],
  model: null,
  client_message_id: "name-1",
  client_location: null,
  client_latitude: null,
  client_longitude: null,
};

const REGENERATE = {
  model: null,
  client_location: null,
  client_latitude: null,
  client_longitude: null,
};

function sentFrames(socket: FakeSocket): unknown[] {
  return socket.send.mock.calls.map(([data]) => JSON.parse(data as string));
}

/** Open the transport's socket; `answersPing`: its server answers the connect ping. */
async function openTransport(answersPing = false) {
  const setup = setupTransport();
  const connecting = setup.transport.connect();
  setup.socket.open();
  await connecting;
  if (answersPing) setup.socket.emit({ type: "pong" });
  return setup;
}

describe("ChatWsTransport", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it("opens, authenticates, pings, serializes turn frames, and parses payloads", async () => {
    const { socket, transport, onPayload } = setupTransport();
    const connecting = transport.connect();

    socket.open();
    await connecting;

    expect(transport.isOpen()).toBe(true);
    expect(socket.send).toHaveBeenNthCalledWith(
      1,
      JSON.stringify({ token: "token", client_timezone: "UTC" }),
    );
    // Its pong says the server can be probed later; the frame is not a turn.
    expect(socket.send).toHaveBeenNthCalledWith(2, JSON.stringify({ type: "ping" }));
    socket.emit({ type: "pong" });
    expect(onPayload).not.toHaveBeenCalled();

    expect(transport.sendMessage({
      ...MESSAGE,
      attachment_ids: ["attachment"],
      model: "smart-chat",
      client_location: "Here",
      client_latitude: 1,
      client_longitude: 2,
    })).toBe(true);
    socket.emit({ type: "token", content: "answer" });

    expect(socket.send).toHaveBeenNthCalledWith(
      3,
      JSON.stringify({
        type: "message",
        content: "hello",
        attachment_ids: ["attachment"],
        model: "smart-chat",
        client_message_id: "name-1",
        client_location: "Here",
        client_latitude: 1,
        client_longitude: 2,
      }),
    );
    expect(onPayload).toHaveBeenCalledWith({
      type: "token",
      content: "answer",
    });
  });

  it("sends over SSE after a stalled 900ms handshake, then tries the socket again", async () => {
    const { socket, sockets, transport, onFallback } = setupTransport();
    const connecting = transport.connect();

    jest.advanceTimersByTime(WS_CONNECT_TIMEOUT_MS - 1);
    expect(onFallback).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1);
    await connecting;

    expect(transport.shouldUseSse()).toBe(true);
    expect(socket.close).toHaveBeenCalledTimes(1);
    expect(onFallback).toHaveBeenCalledWith({
      reason: "connect_timeout",
      duringTurn: false,
    });
    void transport.connect();
    expect(sockets).toHaveLength(1);

    jest.advanceTimersByTime(WS_RETRY_BASE_MS);
    expect(transport.shouldUseSse()).toBe(false);
    void transport.connect();
    expect(sockets).toHaveLength(2);
  });

  it("times out an OPEN but silent turn and ignores its late frames", async () => {
    const { socket, transport, onPayload, onFallback } = await openTransport();

    transport.sendRegenerate(REGENERATE);
    socket.onmessage({ data: "not-json" });
    socket.emit({ type: "ping" });
    jest.advanceTimersByTime(WS_FIRST_EVENT_TIMEOUT_MS);

    expect(transport.shouldUseSse()).toBe(true);
    expect(onFallback).toHaveBeenCalledWith({
      reason: "first_event_timeout",
      duringTurn: true,
    });
    expect(socket.close).toHaveBeenCalledTimes(1);
    // A server that never answered the connect ping is never probed.
    expect(sentFrames(socket).filter((frame) => (frame as { type?: string }).type === "ping")).toHaveLength(1);

    socket.emit({ type: "done", message_id: "late" });
    expect(onPayload).toHaveBeenCalledTimes(1);
    expect(onPayload).toHaveBeenCalledWith({ type: "ping" });
  });

  it("clears the first-event deadline after a turn acknowledgment", async () => {
    const { socket, transport, onFallback } = await openTransport(true);

    transport.sendRegenerate(REGENERATE);
    socket.emit({ type: "start" });
    jest.advanceTimersByTime(5 * WS_FIRST_EVENT_TIMEOUT_MS);

    expect(onFallback).not.toHaveBeenCalled();
    expect(socket.close).not.toHaveBeenCalled();
    expect(sentFrames(socket).at(-1)).toEqual({ type: "regenerate", ...REGENERATE });
  });

  it("probes a quiet send and drops the socket when the ping goes unanswered", async () => {
    const { socket, transport, onFallback } = await openTransport(true);

    transport.sendMessage(MESSAGE);
    jest.advanceTimersByTime(WS_ACK_PROBE_MS - 1);
    expect(sentFrames(socket).at(-1)).toMatchObject({ type: "message" });
    jest.advanceTimersByTime(1);
    expect(sentFrames(socket).at(-1)).toEqual({ type: "ping" });
    expect(onFallback).not.toHaveBeenCalled();

    jest.advanceTimersByTime(WS_PROBE_TIMEOUT_MS);
    expect(onFallback).toHaveBeenCalledTimes(1);
    expect(onFallback).toHaveBeenCalledWith({ reason: "unresponsive", duringTurn: true });
    expect(socket.close).toHaveBeenCalledTimes(1);
    expect(transport.isTurnActive()).toBe(false);
    expect(transport.shouldUseSse()).toBe(true);
    // The 30 s deadline went with the socket.
    jest.advanceTimersByTime(WS_FIRST_EVENT_TIMEOUT_MS);
    expect(onFallback).toHaveBeenCalledTimes(1);
  });

  it("keeps a socket that answers the probe, and its last-resort deadline", async () => {
    const { socket, transport, onFallback } = await openTransport(true);

    transport.sendMessage(MESSAGE);
    jest.advanceTimersByTime(WS_ACK_PROBE_MS);
    socket.emit({ type: "pong" });
    jest.advanceTimersByTime(WS_PROBE_TIMEOUT_MS);
    expect(onFallback).not.toHaveBeenCalled();
    expect(transport.isOpen()).toBe(true);

    jest.advanceTimersByTime(WS_FIRST_EVENT_TIMEOUT_MS);
    expect(onFallback).toHaveBeenCalledWith({ reason: "first_event_timeout", duringTurn: true });
  });

  it("probes a quiet send on a fresh socket as soon as its late connect pong comes", async () => {
    const { socket, transport, onFallback } = await openTransport();
    transport.sendMessage(MESSAGE);
    jest.advanceTimersByTime(WS_ACK_PROBE_MS);
    expect(sentFrames(socket).at(-1)).toMatchObject({ type: "message" });

    socket.emit({ type: "pong" });
    expect(sentFrames(socket).at(-1)).toEqual({ type: "ping" });
    jest.advanceTimersByTime(WS_PROBE_TIMEOUT_MS);
    expect(onFallback).toHaveBeenCalledWith({ reason: "unresponsive", duringTurn: true });
  });

  it("does not probe on a late pong once the send was acknowledged", async () => {
    const { socket, transport, onFallback } = await openTransport();
    transport.sendMessage(MESSAGE);
    jest.advanceTimersByTime(WS_ACK_PROBE_MS);
    socket.emit({ type: "start" });
    socket.emit({ type: "pong" });
    jest.advanceTimersByTime(WS_PROBE_TIMEOUT_MS);

    expect(sentFrames(socket).at(-1)).toMatchObject({ type: "message" });
    expect(onFallback).not.toHaveBeenCalled();
  });

  it("drops no socket for a probe the user's Stop overtook", async () => {
    const { socket, transport, onFallback } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    jest.advanceTimersByTime(WS_ACK_PROBE_MS);
    expect(sentFrames(socket).at(-1)).toEqual({ type: "ping" });
    transport.cancel();
    jest.advanceTimersByTime(WS_FIRST_EVENT_TIMEOUT_MS);

    expect(onFallback).not.toHaveBeenCalled();
    expect(transport.isOpen()).toBe(true);
    expect(sentFrames(socket).at(-1)).toEqual({ type: "cancel" });
  });

  it("expects a saved reply's follow-up questions until they come, or for 10 s", async () => {
    const { socket, transport } = await openTransport();
    expect(transport.expectsFollowUps()).toBe(false);
    socket.emit({ type: "done", message_id: "saved" });
    expect(transport.expectsFollowUps()).toBe(true);
    socket.emit({ type: "related_prompts", message_id: "saved", prompts: ["Why?"] });
    expect(transport.expectsFollowUps()).toBe(false);

    socket.emit({ type: "done", message_id: "saved-2" });
    jest.advanceTimersByTime(WS_FOLLOW_UPS_WAIT_MS);
    expect(transport.expectsFollowUps()).toBe(false);
    // A reply still saving (no id) gets none; a closed socket brings none.
    socket.emit({ type: "done", persisting: true });
    expect(transport.expectsFollowUps()).toBe(false);
    socket.emit({ type: "done", message_id: "saved-3" });
    (socket.onclose as (event: { code: number }) => void)({ code: 4408 });
    expect(transport.expectsFollowUps()).toBe(false);
  });

  it("does not probe a send the server acknowledged in time", async () => {
    const { socket, transport, onFallback } = await openTransport(true);

    transport.sendMessage(MESSAGE);
    socket.emit({ type: "start" });
    jest.advanceTimersByTime(10 * WS_ACK_PROBE_MS);

    expect(sentFrames(socket).at(-1)).toMatchObject({ type: "message" });
    expect(onFallback).not.toHaveBeenCalled();
  });

  it("probes on request mid-turn and only while a turn is waiting", async () => {
    const { socket, transport, onFallback } = await openTransport(true);
    transport.probe();
    expect(sentFrames(socket).filter((frame) => (frame as { type?: string }).type === "ping")).toHaveLength(1);

    transport.sendMessage(MESSAGE);
    socket.emit({ type: "start" });
    socket.emit({ type: "token", content: "partial" });
    transport.probe();
    transport.probe();
    expect(sentFrames(socket).at(-1)).toEqual({ type: "ping" });
    expect(sentFrames(socket).filter((frame) => (frame as { type?: string }).type === "ping")).toHaveLength(2);
    jest.advanceTimersByTime(WS_PROBE_TIMEOUT_MS);

    expect(onFallback).toHaveBeenCalledWith({ reason: "unresponsive", duringTurn: true });
  });

  it("probes again instead of dropping when the deadline fired late (app suspended)", async () => {
    const { socket, transport, onFallback } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    socket.emit({ type: "start" });

    transport.probe();
    jest.setSystemTime(Date.now() + 10 * WS_PROBE_TIMEOUT_MS);
    jest.advanceTimersByTime(WS_PROBE_TIMEOUT_MS);
    expect(onFallback).not.toHaveBeenCalled();
    expect(sentFrames(socket).filter((frame) => (frame as { type?: string }).type === "ping")).toHaveLength(3);

    socket.emit({ type: "token", content: "still here" });
    jest.advanceTimersByTime(WS_PROBE_TIMEOUT_MS);
    expect(onFallback).not.toHaveBeenCalled();
  });

  it("ends the turn on duplicate: the server follows the earlier send", async () => {
    const { socket, transport, onPayload, onFallback } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    socket.emit({ type: "duplicate" });
    jest.advanceTimersByTime(WS_FIRST_EVENT_TIMEOUT_MS);

    expect(transport.isTurnActive()).toBe(false);
    expect(onPayload).toHaveBeenCalledWith({ type: "duplicate" });
    expect(onFallback).not.toHaveBeenCalled();
    expect(sentFrames(socket).at(-1)).toMatchObject({ type: "message" });
  });

  it("signals auth rejection once and never delivers it as a normal payload", async () => {
    const { socket, transport, onPayload, onFallback } = await openTransport();

    transport.sendRegenerate(REGENERATE);
    socket.emit({ type: "error", message: "Unauthorized" });
    socket.onclose();

    expect(onPayload).not.toHaveBeenCalled();
    expect(onFallback).toHaveBeenCalledTimes(1);
    expect(onFallback).toHaveBeenCalledWith({
      reason: "unauthorized",
      duringTurn: true,
      payload: { type: "error", message: "Unauthorized" },
    });
    // Waiting does not help a refused token: a refreshed one builds a new transport.
    jest.advanceTimersByTime(WS_RETRY_MAX_MS);
    expect(transport.shouldUseSse()).toBe(true);
  });

  it.each([
    [4408, "closed_unread"],
    [1012, "disconnect"],
    [1001, "disconnect"],
  ] as const)("a deliberate %i close reconnects on the next send instead of falling back to SSE", async (code, reason) => {
    const { socket, transport, onFallback } = await openTransport();

    (socket.onclose as (event: { code: number }) => void)({ code });

    expect(onFallback).toHaveBeenCalledWith({ reason, duringTurn: false });
    expect(transport.shouldUseSse()).toBe(false);
    expect(transport.isOpen()).toBe(false);
  });

  it("an idle close during a send says the turn was in flight", async () => {
    const { socket, transport, onFallback } = await openTransport();
    transport.sendRegenerate(REGENERATE);

    (socket.onclose as (event: { code: number }) => void)({ code: 4408 });

    expect(onFallback).toHaveBeenCalledWith({ reason: "closed_unread", duringTurn: true });
  });

  it.each([
    [1006, "disconnect"],
    [4429, "closed_unread"],
  ] as const)("any other %i close sends over SSE for a while, then tries the socket again", async (code, reason) => {
    const { socket, transport, onFallback } = await openTransport();

    (socket.onclose as (event: { code: number }) => void)({ code });

    expect(transport.shouldUseSse()).toBe(true);
    expect(onFallback).toHaveBeenCalledWith({ reason, duringTurn: false });
    jest.advanceTimersByTime(WS_RETRY_BASE_MS);
    expect(transport.shouldUseSse()).toBe(false);
  });

  it("keeps a replaced socket's late events away from the socket that took its place", async () => {
    const { socket, sockets, transport, onFallback } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    jest.advanceTimersByTime(WS_ACK_PROBE_MS + WS_PROBE_TIMEOUT_MS);
    expect(onFallback).toHaveBeenLastCalledWith({ reason: "unresponsive", duringTurn: true });
    jest.advanceTimersByTime(WS_RETRY_BASE_MS);

    const reconnecting = transport.connect();
    const next = sockets[1];
    socket.onopen();
    socket.onclose();
    next.open();
    await reconnecting;
    next.emit({ type: "pong" });
    transport.sendMessage(MESSAGE);
    socket.onerror();

    jest.advanceTimersByTime(WS_ACK_PROBE_MS);
    expect(sentFrames(next).at(-1)).toEqual({ type: "ping" });
    expect(onFallback).toHaveBeenCalledTimes(1);
  });

  // S7.11: the server saves a stopped reply as long as the phone drew it.
  it("tells the server how much of the reply the phone kept when it cancels", async () => {
    const { socket, transport } = await openTransport();

    transport.sendMessage({ ...MESSAGE, content: "hi" });
    transport.cancel(42);

    expect(socket.send).toHaveBeenLastCalledWith(
      JSON.stringify({ type: "cancel", shown_chars: 42 }),
    );
  });

  it("stops probing a turn the user stopped", async () => {
    const { socket, transport, onFallback } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    transport.cancel();
    jest.advanceTimersByTime(WS_FIRST_EVENT_TIMEOUT_MS);

    expect(sentFrames(socket).at(-1)).toEqual({ type: "cancel" });
    expect(onFallback).not.toHaveBeenCalled();
  });

  it("sends cancel and detaches callbacks on intentional close", async () => {
    const { socket, transport, onPayload, onFallback } = await openTransport(true);

    transport.sendRegenerate(REGENERATE);
    transport.cancel();
    transport.close();
    socket.onclose();
    socket.emit({ type: "done", message_id: "late" });
    jest.advanceTimersByTime(WS_FIRST_EVENT_TIMEOUT_MS);

    expect(socket.send).toHaveBeenLastCalledWith(JSON.stringify({ type: "cancel" }));
    expect(onPayload).not.toHaveBeenCalled();
    expect(onFallback).not.toHaveBeenCalled();
  });
});
