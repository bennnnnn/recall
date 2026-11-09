import {
  parseChatWsPayload,
  type ChatWsPayload,
} from "@/features/chat/model/socketReduce";
import { createWsBackoff, type WsBackoff } from "@/features/chat/model/wsBackoff";
import {
  STREAM_IDLE_TIMEOUT_MS,
  WS_ACK_PROBE_MS,
  WS_CONNECT_TIMEOUT_MS,
  WS_FIRST_EVENT_TIMEOUT_MS,
  WS_FOLLOW_UPS_WAIT_MS,
  WS_IDLE_KEEP_MS,
  WS_LINGER_MS,
  WS_PROBE_TIMEOUT_MS,
} from "@/features/chat/model/wsConnect";
import { reportConnectionAnswered, reportConnectionFailure } from "@/lib/api/connectionFailures";
import { UNAVAILABLE_CODE } from "@/lib/api/errorBody";
import { getSessionGeneration } from "@/lib/auth";
import { newRequestId, withRequestId } from "@/lib/api/requestId";
import { noteApiFailure } from "@/lib/sentry";
import {
  OUTAGE_CLOSE_CODES,
  RECONNECT_CLOSE_CODES,
  UNREAD_CLOSE_CODES,
  WS_TURN_EVENT_TYPES,
  WS_UNAUTHORIZED_CODE,
  type ChatWsAuthFrame,
  type ChatWsMessageFrame,
  type ChatWsRegenerateFrame,
} from "@/features/chat/model/wsFrames";

const WS_OPEN_STATE = 1;

export type ChatWsFallbackSignal =
  | { reason: "connect_timeout"; duringTurn: false }
  | { reason: "disconnect"; duringTurn: boolean }
  | { reason: "closed_unread"; duringTurn: boolean }
  | {
      reason: "unauthorized";
      duringTurn: boolean;
      payload: ChatWsPayload;
    }
  | { reason: "first_event_timeout"; duringTurn: true }
  /** A probe's ping went unanswered: the socket is dead (see `probe`). */
  | { reason: "unresponsive"; duringTurn: boolean };

/** How a send on a socket is replayed when the socket fails it before `start`. */
export type WsSendFallback = {
  transport: ChatWsTransport;
  retry: () => Promise<void>;
  /** The send carries its client message id: a replay after a dead probe cannot run twice. */
  idempotent?: boolean;
};

type ChatWsTransportOptions = {
  url: string;
  /** The newest bearer token, read when the socket authenticates. */
  getToken: () => string | null;
  /** The phone's zone now, read as each socket authenticates and each turn is sent. */
  clientTimezone: () => string;
  onPayload: (payload: ChatWsPayload) => void;
  onFallback: (signal: ChatWsFallbackSignal) => void;
  createSocket?: (url: string) => WebSocket;
  /** When the socket may be tried again after a failure; one view's transports share it. */
  backoff?: WsBackoff;
  /** The chat is on screen: a socket idle after a turn is kept for the next one (`WS_IDLE_KEEP_MS`). */
  inView?: () => boolean;
};

/**
 * Owns raw WebSocket IO and deadlines. Chat/UI policy stays with the caller
 * through typed payload and fallback callbacks.
 */
export class ChatWsTransport {
  private socket: WebSocket | null = null;
  private connectPromise: Promise<void> | null = null;
  private settleConnect: (() => void) | null = null;
  private connectTimer: ReturnType<typeof setTimeout> | null = null;
  private firstEventTimer: ReturnType<typeof setTimeout> | null = null;
  private ackProbeTimer: ReturnType<typeof setTimeout> | null = null;
  private probeTimer: ReturnType<typeof setTimeout> | null = null;
  /** Once the turn has spoken, the wait for its next event (`STREAM_IDLE_TIMEOUT_MS`). */
  private idleTimer: ReturnType<typeof setTimeout> | null = null;
  private turnActive = false;
  /** The user stopped the turn: its end is waited for, but its loss is nobody's news. */
  private turnStopped = false;
  /** The server refused this transport's token; a refreshed token gets a new transport. */
  private authRejected = false;
  /** The current socket's server answered the connect ping, so it can be probed. */
  private answersPing = false;
  /** The send went quiet before that answer came: probe as soon as it does. */
  private probeOnPong = false;
  /**
   * What a saved reply's `done` says follows it on this socket (its follow-up questions, and
   * a new chat's title when `title_pending`), until then at the latest. Past that, or once
   * they all came, the socket has nothing left to carry and is let go (`releaseWhenQuiet`).
   */
  private followUpsUntil = 0;
  private followUpsDue = new Set<string>();
  /**
   * A socket just opened is kept this long for the send it was opened for, and one whose turn
   * ended, while its chat is on screen, for the conversation's next message.
   */
  private lingerUntil = 0;
  private releaseTimer: ReturnType<typeof setTimeout> | null = null;
  /** Frames the current socket delivered: a probe is answered when this moves. */
  private framesSeen = 0;
  private closed = false;
  private readonly backoff: WsBackoff;

  constructor(private readonly options: ChatWsTransportOptions) {
    this.backoff = options.backoff ?? createWsBackoff();
  }

  isOpen(): boolean {
    return this.socket?.readyState === WS_OPEN_STATE;
  }

  /** Sends go over SSE while the socket cools down after a failure, or once its token was refused. */
  shouldUseSse(): boolean {
    return this.authRejected || this.backoff.cooling();
  }

  /** A message or regenerate frame is still waiting for its done or error. */
  isTurnActive(): boolean {
    return this.turnActive;
  }

  /** The last reply's follow-up questions or title may still arrive: closing now would lose them. */
  expectsFollowUps(): boolean {
    return this.socket !== null && Date.now() < this.followUpsUntil && this.followUpsDue.size > 0;
  }

  /** A socket that names itself, so the API's lines for this connection and the crumb an
   * outage it meets leaves can be found by one id. */
  private openNamedSocket(): { socket: WebSocket; requestId: string } {
    const requestId = newRequestId();
    const create = this.options.createSocket ?? ((url: string) => new WebSocket(url));
    return { socket: create(withRequestId(this.options.url, requestId)), requestId };
  }

  connect(): Promise<void> {
    if (this.closed || this.shouldUseSse() || this.isOpen()) {
      return Promise.resolve();
    }
    if (this.connectPromise) return this.connectPromise;

    const { socket, requestId } = this.openNamedSocket();
    this.socket = socket;
    this.answersPing = false;
    // An outage this socket meets (refused, dropped, or the server's `unavailable` frame and
    // 1013) asks the connection check to look, once, as a request that finds no API does
    // (lib/api/connectionFailures.ts). Its own closes, and an account signed out since, do not.
    // Its server's first frame that is no error (the connect ping's pong) is an answer.
    const openedAt = Date.now();
    const generation = getSessionGeneration();
    let answered = false;
    let outageReported = false;
    const reportOutage = () => {
      if (outageReported || generation !== getSessionGeneration()) return;
      outageReported = true;
      reportConnectionFailure();
      noteApiFailure("WS", this.options.url, null, requestId);
    };
    this.connectPromise = new Promise<void>((resolve) => {
      this.settleConnect = resolve;
    });

    this.connectTimer = setTimeout(() => {
      if (!this.isCurrentSocket(socket)) return;
      this.socket = null;
      this.backoff.fail("connect_timeout");
      this.finishConnect();
      this.options.onFallback({
        reason: "connect_timeout",
        duringTurn: false,
      });
      socket.close();
    }, WS_CONNECT_TIMEOUT_MS);

    // A replaced socket's late events must not touch the timers or the
    // connect wait of the socket that took its place.
    socket.onopen = () => {
      if (!this.isCurrentSocket(socket)) {
        socket.close();
        return;
      }
      this.clearConnectTimer();
      this.sendFrame({
        token: this.options.getToken() ?? "",
        client_timezone: this.options.clientTimezone(),
      } satisfies ChatWsAuthFrame);
      // Its pong says this server can be probed (an older one ignores pings).
      this.sendFrame({ type: "ping" });
      // Opened for a send: one Stop or a left view took back meanwhile is not waited on.
      this.lingerUntil = Date.now() + WS_LINGER_MS;
      this.releaseWhenQuiet();
      this.finishConnect();
    };

    const disconnect = (code?: number) => {
      if (!this.isCurrentSocket(socket)) return;
      this.clearConnectTimer();
      this.clearTurnTimers();
      this.finishConnect();
      const duringTurn = this.turnActive;
      this.socket = null;
      this.turnActive = false;
      if (code === undefined || OUTAGE_CLOSE_CODES.has(code)) reportOutage();
      if (code === undefined || !RECONNECT_CLOSE_CODES.has(code)) this.backoff.fail();
      this.options.onFallback({
        reason: code !== undefined && UNREAD_CLOSE_CODES.has(code) ? "closed_unread" : "disconnect",
        duringTurn,
      });
    };

    socket.onclose = (event?: { code?: number }) => disconnect(event?.code);
    socket.onerror = () => {
      disconnect();
      socket.close();
    };
    socket.onmessage = (event) => {
      if (!this.isCurrentSocket(socket)) return;
      this.framesSeen += 1;
      // React Native and DOM WebSocket both expose `data`, but use different
      // concrete event types. String conversion is the narrow shared boundary.
      const payload = parseChatWsPayload(String(event.data));
      if (!payload) return;
      if (payload.type === "error" && payload.code === UNAVAILABLE_CODE) reportOutage();
      if (payload.type !== "error" && !answered) {
        answered = true;
        reportConnectionAnswered(openedAt);
      }
      if (payload.type === "pong") {
        this.answersPing = true;
        if (this.probeOnPong) {
          this.probeOnPong = false;
          this.probe();
        }
        return;
      }
      if (WS_TURN_EVENT_TYPES.has(payload.type)) {
        this.clearAckTimers();
        if (this.turnActive) this.awaitNextEvent(socket);
      }
      if (payload.type === "keepalive") return;

      if (payload.type === "error" && payload.code === WS_UNAUTHORIZED_CODE) {
        const duringTurn = this.turnActive;
        this.socket = null;
        this.turnActive = false;
        this.authRejected = true;
        this.clearTurnTimers();
        this.options.onFallback({
          reason: "unauthorized",
          duringTurn,
          payload,
        });
        socket.close();
        return;
      }

      if (payload.type === "done" || payload.type === "error" || payload.type === "duplicate") this.endTurn(payload);
      this.followUpsDue.delete(payload.type);
      this.options.onPayload(payload);
      this.releaseWhenQuiet();
    };

    return this.connectPromise;
  }

  sendMessage(frame: Omit<ChatWsMessageFrame, "type" | "client_timezone">): boolean {
    return this.beginTurn({ type: "message", ...frame, client_timezone: this.options.clientTimezone() });
  }

  sendRegenerate(frame: Omit<ChatWsRegenerateFrame, "type" | "client_timezone">): boolean {
    return this.beginTurn({ type: "regenerate", ...frame, client_timezone: this.options.clientTimezone() });
  }

  /**
   * Ask the server to answer at once while a turn waits on this socket. No
   * frame within WS_PROBE_TIMEOUT_MS means the socket is dead: it is dropped
   * with `unresponsive`. Only a socket whose server answered the connect ping
   * is probed; an older server never answers, and that silence proves nothing.
   */
  probe(): void {
    const socket = this.socket;
    if (!socket || !this.isOpen() || !this.turnActive || !this.answersPing || this.probeTimer) return;
    const seen = this.framesSeen;
    const sentAt = Date.now();
    this.sendFrame({ type: "ping" });
    this.probeTimer = setTimeout(() => {
      this.probeTimer = null;
      if (!this.isCurrentSocket(socket) || this.framesSeen !== seen) return;
      // Timers stop while the app is suspended; a deadline that fired late proves nothing.
      if (Date.now() - sentAt > 2 * WS_PROBE_TIMEOUT_MS) {
        this.probe();
        return;
      }
      this.dropUnresponsive(socket);
    }, WS_PROBE_TIMEOUT_MS);
  }

  /**
   * Stop the turn. `shownChars` is how much of the reply the phone drew (the
   * kept bubble's length): the server saves no more than that, so the stopped
   * answer and the saved one are the same text.
   */
  cancel(shownChars?: number): void {
    this.clearTurnTimers();
    if (!this.isOpen()) {
      // Nothing is left to answer the stop.
      this.turnActive = false;
      return;
    }
    this.sendFrame(shownChars == null ? { type: "cancel" } : { type: "cancel", shown_chars: shownChars });
    // The stopped turn ends with its last frame. A socket that never sends one stayed
    // busy for good: kept open in the background, its token never renewed. It gets the
    // turn's silence deadline, and is let go without a word: a drop reported then would
    // land on whatever the chat began since (a Regenerate) and undo it.
    this.turnStopped = true;
    if (this.turnActive && this.socket) this.awaitNextEvent(this.socket);
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.clearConnectTimer();
    this.clearTurnTimers();
    this.clearReleaseTimer();
    this.finishConnect();
    this.turnActive = false;
    const socket = this.socket;
    this.socket = null;
    socket?.close();
  }

  private beginTurn(
    frame: ChatWsMessageFrame | ChatWsRegenerateFrame,
  ): boolean {
    if (!this.isOpen()) return false;
    this.turnActive = true;
    this.turnStopped = false;
    this.lingerUntil = 0;
    this.clearTurnTimers();
    this.clearReleaseTimer();
    this.firstEventTimer = setTimeout(() => {
      if (!this.turnActive || !this.socket) return;
      const socket = this.socket;
      this.firstEventTimer = null;
      this.socket = null;
      this.turnActive = false;
      this.clearTurnTimers();
      this.backoff.fail();
      this.options.onFallback({
        reason: "first_event_timeout",
        duringTurn: true,
      });
      socket.close();
    }, WS_FIRST_EVENT_TIMEOUT_MS);
    // A server that answers sends `start` at once: a quiet send is probed long
    // before the deadline above (a half-open socket used to mean 30 s of dots).
    this.ackProbeTimer = setTimeout(() => {
      this.ackProbeTimer = null;
      // A fresh socket's connect pong can still be on its way.
      if (this.answersPing) this.probe();
      else this.probeOnPong = true;
    }, WS_ACK_PROBE_MS);
    this.sendFrame(frame);
    return true;
  }

  /**
   * The turn's last frame. After a saved reply's done the server sends its follow-up questions
   * and, for a new chat, its title: the socket waits for those (`followUpsUntil`).
   */
  private endTurn(last: ChatWsPayload): void {
    this.turnActive = false;
    this.lingerUntil = this.options.inView?.() === false ? 0 : Date.now() + WS_IDLE_KEEP_MS;
    this.clearTurnTimers();
    if (last.type !== "done") return;
    this.backoff.succeed();
    this.followUpsDue = new Set(last.message_id ? ["related_prompts"] : []);
    if (last.message_id && last.title_pending) this.followUpsDue.add("title");
    this.followUpsUntil = this.followUpsDue.size > 0 ? Date.now() + WS_FOLLOW_UPS_WAIT_MS : 0;
  }

  /**
   * The user left the chat (To-do, Settings, Library): the socket goes once its turn and what
   * follows the turn's done are in, with no idle wait for a next message.
   */
  leftView(): void {
    this.lingerUntil = 0;
    this.releaseWhenQuiet();
  }

  /**
   * A socket with no turn, nothing due after the last one and no next message in sight is
   * closed, as the server closes one idle between turns, and without a word: the next send
   * opens another. An idle socket kept open woke the radio for the server's pings and, left
   * behind a chat the user had moved on from, stayed until the server's 5-minute idle close
   * (2026-11-08 feature test).
   */
  private releaseWhenQuiet(): void {
    this.clearReleaseTimer();
    const socket = this.socket;
    if (!socket || this.turnActive) return;
    const waitMs = Math.max(this.expectsFollowUps() ? this.followUpsUntil : 0, this.lingerUntil) - Date.now();
    if (waitMs > 0) {
      this.releaseTimer = setTimeout(() => this.releaseWhenQuiet(), waitMs);
      return;
    }
    this.socket = null;
    this.followUpsUntil = 0;
    socket.close();
  }

  private clearReleaseTimer(): void {
    if (this.releaseTimer != null) clearTimeout(this.releaseTimer);
    this.releaseTimer = null;
  }

  private dropUnresponsive(socket: WebSocket): void {
    const duringTurn = this.turnActive;
    this.socket = null;
    this.turnActive = false;
    this.clearTurnTimers();
    this.backoff.fail();
    this.options.onFallback({ reason: "unresponsive", duringTurn });
    socket.close();
  }

  private sendFrame(frame: object): void {
    this.socket?.send(JSON.stringify(frame));
  }

  private isCurrentSocket(socket: WebSocket): boolean {
    return !this.closed && this.socket === socket;
  }

  private clearConnectTimer(): void {
    if (this.connectTimer == null) return;
    clearTimeout(this.connectTimer);
    this.connectTimer = null;
  }

  /** The waits for a turn's first event: the deadline and the probe before it. */
  private clearAckTimers(): void {
    this.probeOnPong = false;
    if (this.firstEventTimer != null) clearTimeout(this.firstEventTimer);
    if (this.ackProbeTimer != null) clearTimeout(this.ackProbeTimer);
    this.firstEventTimer = null;
    this.ackProbeTimer = null;
  }

  private clearTurnTimers(): void {
    this.clearAckTimers();
    if (this.probeTimer != null) clearTimeout(this.probeTimer);
    if (this.idleTimer != null) clearTimeout(this.idleTimer);
    this.probeTimer = null;
    this.idleTimer = null;
  }

  /**
   * The turn has spoken: wait for its next event. A silence past the deadline is
   * a dead connection (a network change leaves such a socket behind): close it,
   * report a drop so the caller reloads the chat for the saved reply, and open a
   * new socket for the next send (code-health audit NET-17).
   */
  private awaitNextEvent(socket: WebSocket): void {
    if (this.idleTimer != null) clearTimeout(this.idleTimer);
    this.idleTimer = setTimeout(() => {
      this.idleTimer = null;
      if (!this.turnActive || !this.isCurrentSocket(socket)) return;
      this.socket = null;
      this.turnActive = false;
      this.clearTurnTimers();
      if (!this.turnStopped) this.options.onFallback({ reason: "disconnect", duringTurn: true });
      socket.close();
    }, STREAM_IDLE_TIMEOUT_MS);
  }

  private finishConnect(): void {
    const settle = this.settleConnect;
    this.settleConnect = null;
    this.connectPromise = null;
    settle?.();
  }
}
