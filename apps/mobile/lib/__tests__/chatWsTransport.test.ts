import { WS_CONNECT_TIMEOUT_MS, WS_FIRST_EVENT_TIMEOUT_MS } from "@/lib/chat/wsConnect";
import {
  ChatWsTransport,
  type ChatWsFallbackSignal,
} from "@/lib/chat/wsTransport";

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
  const socket = new FakeSocket();
  const onPayload = jest.fn();
  const onFallback = jest.fn<void, [ChatWsFallbackSignal]>();
  const transport = new ChatWsTransport({
    url: "wss://test/chat",
    token: "token",
    clientTimezone: "UTC",
    onPayload,
    onFallback,
    createSocket: () => socket as unknown as WebSocket,
  });
  return { socket, transport, onPayload, onFallback };
}

describe("ChatWsTransport", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it("opens, authenticates, serializes turn frames, and parses payloads", async () => {
    const { socket, transport, onPayload } = setupTransport();
    const connecting = transport.connect();

    socket.open();
    await connecting;

    expect(transport.isOpen()).toBe(true);
    expect(socket.send).toHaveBeenNthCalledWith(
      1,
      JSON.stringify({ token: "token", client_timezone: "UTC" }),
    );

    expect(transport.sendMessage({
      content: "hello",
      attachment_ids: ["attachment"],
      model: "smart-chat",
      client_location: "Here",
      client_latitude: 1,
      client_longitude: 2,
    })).toBe(true);
    socket.emit({ type: "token", content: "answer" });

    expect(socket.send).toHaveBeenNthCalledWith(
      2,
      JSON.stringify({
        type: "message",
        content: "hello",
        attachment_ids: ["attachment"],
        model: "smart-chat",
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

  it("latches SSE and settles a stalled handshake at 900ms", async () => {
    const { socket, transport, onFallback } = setupTransport();
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
  });

  it("times out an OPEN but silent turn and ignores its late frames", async () => {
    const { socket, transport, onPayload, onFallback } = setupTransport();
    const connecting = transport.connect();
    socket.open();
    await connecting;

    transport.sendRegenerate({
      model: null,
      client_location: null,
      client_latitude: null,
      client_longitude: null,
    });
    socket.onmessage({ data: "not-json" });
    socket.emit({ type: "ping" });
    jest.advanceTimersByTime(WS_FIRST_EVENT_TIMEOUT_MS);

    expect(transport.shouldUseSse()).toBe(true);
    expect(onFallback).toHaveBeenCalledWith({
      reason: "first_event_timeout",
      duringTurn: true,
    });
    expect(socket.close).toHaveBeenCalledTimes(1);

    socket.emit({ type: "done", message_id: "late" });
    expect(onPayload).toHaveBeenCalledTimes(1);
    expect(onPayload).toHaveBeenCalledWith({ type: "ping" });
  });

  it("clears the first-event deadline after a turn acknowledgment", async () => {
    const { socket, transport, onFallback } = setupTransport();
    const connecting = transport.connect();
    socket.open();
    await connecting;

    transport.sendRegenerate({
      model: null,
      client_location: null,
      client_latitude: null,
      client_longitude: null,
    });
    socket.emit({ type: "start" });
    jest.advanceTimersByTime(5 * WS_FIRST_EVENT_TIMEOUT_MS);

    expect(onFallback).not.toHaveBeenCalled();
    expect(socket.close).not.toHaveBeenCalled();
  });

  it("signals auth rejection once and never delivers it as a normal payload", async () => {
    const { socket, transport, onPayload, onFallback } = setupTransport();
    const connecting = transport.connect();
    socket.open();
    await connecting;

    transport.sendRegenerate({
      model: null,
      client_location: null,
      client_latitude: null,
      client_longitude: null,
    });
    socket.emit({ type: "error", message: "Unauthorized" });
    socket.onclose();

    expect(onPayload).not.toHaveBeenCalled();
    expect(onFallback).toHaveBeenCalledTimes(1);
    expect(onFallback).toHaveBeenCalledWith({
      reason: "unauthorized",
      duringTurn: true,
      payload: { type: "error", message: "Unauthorized" },
    });
    expect(transport.shouldUseSse()).toBe(true);
  });

  it("sends cancel and detaches callbacks on intentional close", async () => {
    const { socket, transport, onPayload, onFallback } = setupTransport();
    const connecting = transport.connect();
    socket.open();
    await connecting;

    transport.sendRegenerate({
      model: null,
      client_location: null,
      client_latitude: null,
      client_longitude: null,
    });
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
