import {
  createWsBackoff,
  WS_CONNECT_TIMEOUT_RETRY_MS,
  WS_RETRY_BASE_MS,
  WS_RETRY_MAX_MS,
} from "@/features/chat/model/wsBackoff";
import {
  ANSWER_PHOTO_WAIT_MS,
  STREAM_IDLE_TIMEOUT_MS,
  WS_ACK_PROBE_MS,
  WS_CONNECT_TIMEOUT_MS,
  WS_FIRST_EVENT_TIMEOUT_MS,
  WS_FOLLOW_UPS_WAIT_MS,
  WS_IDLE_KEEP_MS,
  WS_LINGER_MS,
  WS_PROBE_TIMEOUT_MS,
} from "@/features/chat/model/wsConnect";
import {
  ChatWsTransport,
  type ChatWsFallbackSignal,
} from "@/features/chat/model/wsTransport";
import { onConnectionAnswered, onConnectionFailure } from "@/lib/api/connectionFailures";

let mockSession = 0;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
const mockNoteApiFailure = jest.fn();
jest.mock("@/lib/sentry", () => ({
  noteApiFailure: (...args: unknown[]) => mockNoteApiFailure(...args),
}));

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

function setupTransport(inView?: () => boolean) {
  // The first socket is ready before connect(); each later connect gets a new one.
  const socket = new FakeSocket();
  const sockets = [socket];
  let handedOut = 0;
  const onPayload = jest.fn();
  const onFallback = jest.fn<void, [ChatWsFallbackSignal]>();
  const transport = new ChatWsTransport({
    url: "wss://test/chat",
    getToken: () => "token",
    clientTimezone: () => "UTC",
    onPayload,
    onFallback,
    backoff: createWsBackoff(),
    inView,
    createSocket: () => {
      if (handedOut > 0) sockets.push(new FakeSocket());
      return sockets[handedOut++] as unknown as WebSocket;
    },
  });
  return { socket, sockets, transport, onPayload, onFallback };
}

describe("socket ids", () => {
  it("names each connection in its URL", async () => {
    const urls: string[] = [];
    const socket = new FakeSocket();
    const transport = new ChatWsTransport({
      url: "wss://test/chat",
      getToken: () => "token",
      clientTimezone: () => "UTC",
      onPayload: jest.fn(),
      onFallback: jest.fn(),
      backoff: createWsBackoff(),
      createSocket: (url) => {
        urls.push(url);
        return socket as unknown as WebSocket;
      },
    });
    void transport.connect();
    expect(urls).toHaveLength(1);
    expect(urls[0]).toMatch(/^wss:\/\/test\/chat\?request_id=[A-Za-z0-9_-]{1,64}$/);
    transport.close();
  });
});

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
async function openTransport(answersPing = false, inView?: () => boolean) {
  const setup = setupTransport(inView);
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
        client_timezone: "UTC",
      }),
    );
    expect(onPayload).toHaveBeenCalledWith({
      type: "token",
      content: "answer",
    });
  });

  it("sends over SSE after a stalled handshake, then soon tries the socket again", async () => {
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

    // One slow handshake is not a broken path: the wait is short.
    jest.advanceTimersByTime(WS_CONNECT_TIMEOUT_RETRY_MS);
    expect(transport.shouldUseSse()).toBe(false);
    const again = transport.connect();
    expect(sockets).toHaveLength(2);

    // A second stalled handshake in a row waits as any failure does.
    jest.advanceTimersByTime(WS_CONNECT_TIMEOUT_MS);
    await again;
    jest.advanceTimersByTime(WS_RETRY_BASE_MS);
    expect(transport.shouldUseSse()).toBe(true);
    jest.advanceTimersByTime(WS_RETRY_BASE_MS);
    expect(transport.shouldUseSse()).toBe(false);
  });

  it("opens a handshake that takes longer than a second on a slow network", async () => {
    const { socket, transport, onFallback } = setupTransport();
    const connecting = transport.connect();
    jest.advanceTimersByTime(1_500);
    socket.open();
    await connecting;
    expect(onFallback).not.toHaveBeenCalled();
    expect(transport.isOpen()).toBe(true);
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

  it("after a turn acknowledgment waits for each next event, keepalives included", async () => {
    const { socket, transport, onPayload, onFallback } = setupTransport();
    const connecting = transport.connect();
    socket.open();
    await connecting;

    transport.sendRegenerate(REGENERATE);
    socket.emit({ type: "start" });
    // The first-event deadline is gone; the idle one is longer.
    jest.advanceTimersByTime(STREAM_IDLE_TIMEOUT_MS - 1);
    socket.emit({ type: "keepalive" });
    jest.advanceTimersByTime(STREAM_IDLE_TIMEOUT_MS - 1);
    socket.emit({ type: "token", content: "slow" });
    jest.advanceTimersByTime(STREAM_IDLE_TIMEOUT_MS - 1);

    expect(onFallback).not.toHaveBeenCalled();
    expect(socket.close).not.toHaveBeenCalled();
    // A keepalive is proof of life, not a payload.
    expect(onPayload.mock.calls.map(([payload]) => payload.type)).toEqual(["start", "token"]);
  });

  it("drops a turn quiet past the idle deadline and opens a new socket next time", async () => {
    const { socket, transport, onPayload, onFallback } = setupTransport();
    const connecting = transport.connect();
    socket.open();
    await connecting;

    transport.sendMessage(MESSAGE);
    socket.emit({ type: "start" });
    socket.emit({ type: "token", content: "par" });
    jest.advanceTimersByTime(STREAM_IDLE_TIMEOUT_MS);

    expect(onFallback).toHaveBeenCalledWith({ reason: "disconnect", duringTurn: true });
    expect(socket.close).toHaveBeenCalledTimes(1);
    expect(transport.isTurnActive()).toBe(false);
    expect(transport.shouldUseSse()).toBe(false);
    // Late frames from the dropped socket are not this turn's any more.
    socket.emit({ type: "done", message_id: "late" });
    expect(onPayload).toHaveBeenCalledTimes(2);
  });

  it("puts no deadline on a finished turn: its socket is let go without a word", async () => {
    const { socket, transport, onFallback } = setupTransport();
    const connecting = transport.connect();
    socket.open();
    await connecting;

    transport.sendRegenerate(REGENERATE);
    socket.emit({ type: "start" });
    socket.emit({ type: "done", message_id: "m1" });
    jest.advanceTimersByTime(5 * STREAM_IDLE_TIMEOUT_MS);

    expect(onFallback).not.toHaveBeenCalled();
    expect(socket.close).toHaveBeenCalledTimes(1);
    expect(transport.isOpen()).toBe(false);
    expect(sentFrames(socket).at(-1)).toEqual({ type: "regenerate", ...REGENERATE, client_timezone: "UTC" });
  });

  // 2026-11-08 feature test: a chat's socket opened on its first keystroke or when it was only
  // read, and stayed open behind the chat the user moved on from until the server's 5-minute
  // idle close (49 opens in 48 turns). It lives for its turn and what follows its done.
  describe("a socket's life", () => {
    /** The chat on screen (true) or under To-do, Settings, Library (false), as the hook says. */
    let inView = true;
    const sentTurn = async () => {
      const setup = await openTransport(true, () => inView);
      setup.transport.sendMessage(MESSAGE);
      setup.socket.emit({ type: "start" });
      return setup;
    };
    beforeEach(() => {
      inView = true;
    });

    it("is kept a minute after its turn while the chat is on screen, then let go", async () => {
      const { socket, transport, onFallback } = await sentTurn();
      socket.emit({ type: "done", message_id: "m1", title_pending: "1" });
      socket.emit({ type: "related_prompts", message_id: "m1", prompts: ["Why?"] });
      socket.emit({ type: "title", title: "Heater repair" });
      jest.advanceTimersByTime(WS_IDLE_KEEP_MS - 1);
      expect(socket.close).not.toHaveBeenCalled();
      jest.advanceTimersByTime(1);
      expect(socket.close).toHaveBeenCalledTimes(1);
      expect(transport.isOpen()).toBe(false);
      expect(onFallback).not.toHaveBeenCalled();
    });

    it("carries the conversation's next message within the minute, and keeps it for the one after", async () => {
      const { socket, transport } = await sentTurn();
      socket.emit({ type: "done", message_id: "m1" });
      jest.advanceTimersByTime(WS_IDLE_KEEP_MS - 1_000);
      expect(transport.sendMessage({ ...MESSAGE, client_message_id: "name-2" })).toBe(true);
      socket.emit({ type: "start" });
      socket.emit({ type: "done", persisting: true });
      jest.advanceTimersByTime(WS_IDLE_KEEP_MS - 1);
      expect(socket.close).not.toHaveBeenCalled();
      jest.advanceTimersByTime(1);
      expect(socket.close).toHaveBeenCalledTimes(1);
    });

    it.each([
      ["a reply still saving", { type: "done", persisting: true }],
      ["an error", { type: "error", message: "nope" }],
      ["a duplicate", { type: "duplicate" }],
    ])("is kept for a Retry or the next message after %s", async (_label, frame) => {
      const { socket, onFallback } = await sentTurn();
      socket.emit(frame);
      jest.advanceTimersByTime(WS_IDLE_KEEP_MS - 1);
      expect(socket.close).not.toHaveBeenCalled();
      jest.advanceTimersByTime(1);
      expect(socket.close).toHaveBeenCalledTimes(1);
      expect(onFallback).not.toHaveBeenCalled();
    });

    it("is let go at once when the user leaves the chat with nothing due", async () => {
      const { socket, transport } = await sentTurn();
      socket.emit({ type: "done", persisting: true });
      inView = false;
      transport.leftView();
      expect(socket.close).toHaveBeenCalledTimes(1);
    });

    it("left during a turn, is let go once the turn's follow-ups and title are in", async () => {
      const { socket, transport } = await sentTurn();
      inView = false;
      transport.leftView();
      expect(socket.close).not.toHaveBeenCalled();
      socket.emit({ type: "done", message_id: "m1", title_pending: "1" });
      socket.emit({ type: "related_prompts", message_id: "m1", prompts: ["Why?"] });
      expect(socket.close).not.toHaveBeenCalled();
      socket.emit({ type: "title", title: "Heater repair" });
      expect(socket.close).toHaveBeenCalledTimes(1);
    });

    // 2026-11-09: the reply's photo was still on its way when the reply went out.
    it("carries a photo that comes after its reply while the chat is on screen", async () => {
      const { socket, onPayload } = await sentTurn();
      socket.emit({ type: "done", message_id: "m1", photo_pending: "1" });
      socket.emit({ type: "related_prompts", message_id: "m1", prompts: ["Why?"] });
      jest.advanceTimersByTime(ANSWER_PHOTO_WAIT_MS - 1);
      expect(socket.close).not.toHaveBeenCalled();
      socket.emit({ type: "answer_photo", message_id: "m1", content: "[Image: /attachments/p/file]\n\nHi" });
      expect(onPayload).toHaveBeenLastCalledWith(expect.objectContaining({ type: "answer_photo" }));
    });

    it("left, is not kept for a photo still on its way: the saved reply carries it", async () => {
      const { socket, transport } = await sentTurn();
      socket.emit({ type: "done", message_id: "m1", photo_pending: "1" });
      socket.emit({ type: "related_prompts", message_id: "m1", prompts: ["Why?"] });
      inView = false;
      transport.leftView();
      expect(socket.close).toHaveBeenCalledTimes(1);
    });

    it("left, is let go after the follow-ups wait when they never came", async () => {
      const { socket, transport } = await sentTurn();
      socket.emit({ type: "done", message_id: "m1" });
      inView = false;
      transport.leftView();
      jest.advanceTimersByTime(WS_FOLLOW_UPS_WAIT_MS - 1);
      expect(socket.close).not.toHaveBeenCalled();
      jest.advanceTimersByTime(1);
      expect(socket.close).toHaveBeenCalledTimes(1);
    });

    it("opens a new socket for the send after it was let go", async () => {
      const { socket, sockets, transport } = await sentTurn();
      socket.emit({ type: "done", persisting: true });
      transport.leftView();
      expect(transport.isOpen()).toBe(false);
      const connecting = transport.connect();
      expect(sockets).toHaveLength(2);
      sockets[1].open();
      await connecting;
      expect(transport.sendMessage(MESSAGE)).toBe(true);
    });

    it("keeps a socket a draft opened for the idle minute, and one opened after a left view a moment", async () => {
      const { socket } = await openTransport(true, () => inView);
      jest.advanceTimersByTime(WS_IDLE_KEEP_MS - 1);
      expect(socket.close).not.toHaveBeenCalled();
      jest.advanceTimersByTime(1);
      expect(socket.close).toHaveBeenCalledTimes(1);
      inView = false;
      const away = await openTransport(true, () => inView);
      jest.advanceTimersByTime(WS_LINGER_MS);
      expect(away.socket.close).toHaveBeenCalledTimes(1);
    });

    // Review 2026-11-09: a socket closed while connecting left its connect unsettled, and
    // every send after it waited on that connect for good (dots without end).
    it("left during the handshake, still opens, carries the tapped send, and leaves no connect behind", async () => {
      const { socket, sockets, transport } = setupTransport(() => inView);
      let settled = false;
      void transport.connect().then(() => { settled = true; });
      inView = false;
      transport.leftView();
      expect(socket.close).not.toHaveBeenCalled();
      socket.open();
      await Promise.resolve();
      expect(settled).toBe(true);
      expect(transport.sendMessage(MESSAGE)).toBe(true);
      socket.emit({ type: "start" });
      socket.emit({ type: "done", persisting: true });
      expect(socket.close).toHaveBeenCalledTimes(1);
      let later = false;
      void transport.connect().then(() => { later = true; });
      expect(sockets).toHaveLength(2);
      sockets[1].open();
      await Promise.resolve();
      expect(later).toBe(true);
      expect(transport.isOpen()).toBe(true);
    });

    it("settles a connect whose socket closes before it opens, so the next send starts fresh", async () => {
      const { socket, sockets, transport } = setupTransport(() => inView);
      let settled = false;
      void transport.connect().then(() => { settled = true; });
      (socket.onclose as (event: { code: number }) => void)({ code: 1006 });
      await Promise.resolve();
      expect(settled).toBe(true);
      jest.advanceTimersByTime(WS_RETRY_MAX_MS);
      void transport.connect();
      expect(sockets).toHaveLength(2);
    });

    it("leaves no release timer behind a socket the server closed during the idle minute", async () => {
      const { socket, sockets, transport } = await sentTurn();
      socket.emit({ type: "done", message_id: "m1" });
      socket.emit({ type: "related_prompts", message_id: "m1", prompts: [] });
      jest.advanceTimersByTime(30_000);
      // A deploy closes the kept socket (uvicorn's 1012).
      (socket.onclose as (event: { code: number }) => void)({ code: 1012 });
      jest.advanceTimersByTime(WS_IDLE_KEEP_MS / 2 - 200);
      let settled = false;
      void transport.connect().then(() => { settled = true; });
      // The old socket's minute ends while the new one's handshake runs.
      jest.advanceTimersByTime(1_000);
      expect(sockets[1].close).not.toHaveBeenCalled();
      sockets[1].open();
      await Promise.resolve();
      expect(settled).toBe(true);
      expect(transport.isOpen()).toBe(true);
      expect(transport.sendMessage(MESSAGE)).toBe(true);
    });
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
    socket.emit({ type: "error", code: "unauthorized", message: "Unauthorized" });
    socket.onclose();

    expect(onPayload).not.toHaveBeenCalled();
    expect(onFallback).toHaveBeenCalledTimes(1);
    expect(onFallback).toHaveBeenCalledWith({
      reason: "unauthorized",
      duringTurn: true,
      payload: { type: "error", code: "unauthorized", message: "Unauthorized" },
    });
    // Waiting does not help a refused token: a refreshed one builds a new transport.
    jest.advanceTimersByTime(WS_RETRY_MAX_MS);
    expect(transport.shouldUseSse()).toBe(true);
  });

  it("authenticates each new socket with the newest token", async () => {
    let token = "first";
    const sockets: FakeSocket[] = [];
    const transport = new ChatWsTransport({
      url: "wss://test/chat",
      getToken: () => token,
      clientTimezone: () => "UTC",
      onPayload: jest.fn(),
      onFallback: jest.fn(),
      backoff: createWsBackoff(),
      createSocket: () => {
        const socket = new FakeSocket();
        sockets.push(socket);
        return socket as unknown as WebSocket;
      },
    });
    let connecting = transport.connect();
    sockets[0]!.open();
    await connecting;
    // The server closes an idle socket (4408); the token rotated meanwhile.
    (sockets[0]!.onclose as (event?: { code?: number }) => void)({ code: 4408 });
    token = "rotated";
    connecting = transport.connect();
    sockets[1]!.open();
    await connecting;

    expect(sockets[1]!.send).toHaveBeenNthCalledWith(
      1,
      JSON.stringify({ token: "rotated", client_timezone: "UTC" }),
    );
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

  it("ends a stopped turn when its last frame comes", async () => {
    const { socket, transport, onFallback } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    socket.emit({ type: "start" });
    transport.cancel();
    expect(transport.isTurnActive()).toBe(true);
    socket.emit({ type: "done", message_id: "m1" });
    expect(transport.isTurnActive()).toBe(false);
    jest.advanceTimersByTime(5 * STREAM_IDLE_TIMEOUT_MS);
    // Let go once its follow-ups were due, never dropped for the stop.
    expect(socket.close).toHaveBeenCalledTimes(1);
    expect(onFallback).not.toHaveBeenCalled();
  });

  it.each([
    ["nothing more", [] as object[]],
    ["one late token", [{ type: "token", content: "more" }]],
  ])("lets go of a socket that never ends a stopped turn, without a word (%s)", async (_label, late) => {
    const { socket, transport, onFallback } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    socket.emit({ type: "start" });
    socket.emit({ type: "token", content: "par" });
    transport.cancel();
    for (const frame of late) socket.emit(frame);
    jest.advanceTimersByTime(STREAM_IDLE_TIMEOUT_MS);

    // No longer busy: it may be released in the background and its token renewed.
    expect(transport.isTurnActive()).toBe(false);
    expect(socket.close).toHaveBeenCalledTimes(1);
    // A drop reported now would land on whatever the chat began since (a Regenerate).
    expect(onFallback).not.toHaveBeenCalled();
  });

  it("reports a quiet turn begun after a stop as usual", async () => {
    const { socket, transport, onFallback } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    socket.emit({ type: "start" });
    transport.cancel();
    socket.emit({ type: "done", message_id: "m1" });
    transport.sendRegenerate(REGENERATE);
    socket.emit({ type: "start" });
    jest.advanceTimersByTime(STREAM_IDLE_TIMEOUT_MS);
    expect(onFallback).toHaveBeenCalledWith({ reason: "disconnect", duringTurn: true });
  });

  it("is not busy after a stop on a socket that already closed", async () => {
    const { socket, transport } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    socket.readyState = 3;
    transport.cancel();
    expect(transport.isTurnActive()).toBe(false);
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

describe("ChatWsTransport outages and the connection check", () => {
  const closeWith = (socket: FakeSocket, code: number) =>
    (socket.onclose as (event: { code: number }) => void)({ code });
  let reported = 0;
  let stop: () => void = () => {};
  beforeEach(() => {
    jest.useFakeTimers();
    reported = 0;
    stop = onConnectionFailure(() => { reported += 1; });
  });
  afterEach(() => {
    stop();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it("asks for one check when the server's Redis is down: its unavailable frame, then 1013", async () => {
    const { socket, transport, onPayload } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    const frame = { type: "error", code: "unavailable", message: "Down", user_message_saved: false };
    socket.emit(frame);
    closeWith(socket, 1013);
    expect(onPayload).toHaveBeenCalledWith(frame);
    expect(reported).toBe(1);
  });

  it("leaves a crumb with the failed socket's own id", async () => {
    mockNoteApiFailure.mockClear();
    const urls: string[] = [];
    const socket = new FakeSocket();
    const transport = new ChatWsTransport({
      url: "wss://test/chat",
      getToken: () => "token",
      clientTimezone: () => "UTC",
      onPayload: jest.fn(),
      onFallback: jest.fn(),
      backoff: createWsBackoff(),
      createSocket: (url) => {
        urls.push(url);
        return socket as unknown as WebSocket;
      },
    });
    void transport.connect();
    socket.open();
    socket.emit({ type: "pong" });
    socket.emit({ type: "error", code: "unavailable", message: "Down" });
    const id = new URL(urls[0]).searchParams.get("request_id");
    expect(mockNoteApiFailure).toHaveBeenCalledWith("WS", "wss://test/chat", null, id);
    transport.close();
  });

  it("asks for one check for an unavailable frame mid-turn", async () => {
    const { socket, transport } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    socket.emit({ type: "start" });
    socket.emit({ type: "error", code: "unavailable", message: "Down" });
    expect(reported).toBe(1);
  });

  it("asks for one check for a socket refused before it opened", async () => {
    const { socket, transport } = setupTransport();
    const connecting = transport.connect();
    socket.onerror();
    socket.onclose();
    await connecting;
    expect(reported).toBe(1);
  });

  it.each([1006, 1013, 1014])("asks for one check for an open socket closed with %s", async (code) => {
    const { socket } = await openTransport(true);
    closeWith(socket, code);
    expect(reported).toBe(1);
  });

  it("asks for one check for an open socket that errors", async () => {
    const { socket } = await openTransport(true);
    socket.onerror();
    expect(reported).toBe(1);
  });

  it.each([1000, 1001, 1008, 1011, 1012, 4408, 4429])("asks for none for a close with %s", async (code) => {
    const { socket, transport } = await openTransport(true);
    transport.sendMessage(MESSAGE);
    closeWith(socket, code);
    expect(reported).toBe(0);
  });

  it("asks for none for its own closes: a stalled handshake, a quiet turn, Stop and leaving", async () => {
    const stalled = setupTransport();
    const connecting = stalled.transport.connect();
    jest.advanceTimersByTime(WS_CONNECT_TIMEOUT_MS);
    await connecting;
    stalled.socket.onerror();

    const quiet = await openTransport(true);
    quiet.transport.sendMessage(MESSAGE);
    jest.advanceTimersByTime(WS_FIRST_EVENT_TIMEOUT_MS);
    quiet.socket.onerror();

    const stopped = await openTransport(true);
    stopped.transport.sendMessage(MESSAGE);
    stopped.transport.cancel();
    stopped.transport.close();
    closeWith(stopped.socket, 1006);

    const refused = await openTransport(true);
    refused.socket.emit({ type: "error", code: "unauthorized", message: "Unauthorized" });
    closeWith(refused.socket, 1008);
    expect(reported).toBe(0);
  });

  it("says its server answered once, at its first frame that is no error, with when it opened", async () => {
    const answers: number[] = [];
    const stopAnswers = onConnectionAnswered((sentAt) => { answers.push(sentAt); });
    const refused = await openTransport();
    refused.socket.emit({ type: "error", code: "unavailable", message: "Down" });
    expect(answers).toEqual([]);

    const { socket, transport } = setupTransport();
    const openedAt = Date.now();
    const connecting = transport.connect();
    jest.advanceTimersByTime(300);
    socket.open();
    await connecting;
    socket.emit({ type: "pong" });
    transport.sendMessage(MESSAGE);
    socket.emit({ type: "start" });
    stopAnswers();
    expect(answers).toEqual([openedAt]);
  });

  it("asks for none for an account signed out since the socket opened", async () => {
    const { socket } = await openTransport(true);
    mockSession += 1;
    socket.emit({ type: "error", code: "unavailable", message: "Down" });
    closeWith(socket, 1013);
    expect(reported).toBe(0);
  });
});
