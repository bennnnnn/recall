import {
  parseChatWsPayload,
  type ChatWsPayload,
} from "@/lib/chat/socketReduce";
import {
  WS_CONNECT_TIMEOUT_MS,
  WS_FIRST_EVENT_TIMEOUT_MS,
} from "@/lib/chat/wsConnect";

const WS_TURN_EVENT_TYPES = new Set([
  "start",
  "status",
  "token",
  "reasoning",
  "stream_end",
  "done",
  "error",
]);

const WS_OPEN_STATE = 1;

type ChatWsAuthFrame = {
  token: string;
  client_timezone: string;
};

export type ChatWsMessageFrame = {
  type: "message";
  content: string;
  attachment_ids: string[];
  model: string | null;
  client_location: string | null;
  client_latitude: number | null;
  client_longitude: number | null;
};

export type ChatWsRegenerateFrame = {
  type: "regenerate";
  model: string | null;
  client_location: string | null;
  client_latitude: number | null;
  client_longitude: number | null;
};

export type ChatWsFallbackSignal =
  | { reason: "connect_timeout"; duringTurn: false }
  | { reason: "disconnect"; duringTurn: boolean }
  | {
      reason: "unauthorized";
      duringTurn: boolean;
      payload: ChatWsPayload;
    }
  | { reason: "first_event_timeout"; duringTurn: true };

export type ChatWsTransportOptions = {
  url: string;
  token: string;
  clientTimezone: string;
  onPayload: (payload: ChatWsPayload) => void;
  onFallback: (signal: ChatWsFallbackSignal) => void;
  createSocket?: (url: string) => WebSocket;
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
  private turnActive = false;
  private preferSse = false;
  private closed = false;

  constructor(private readonly options: ChatWsTransportOptions) {}

  isOpen(): boolean {
    return this.socket?.readyState === WS_OPEN_STATE;
  }

  shouldUseSse(): boolean {
    return this.preferSse;
  }

  connect(): Promise<void> {
    if (this.closed || this.preferSse || this.isOpen()) {
      return Promise.resolve();
    }
    if (this.connectPromise) return this.connectPromise;

    const socket = (this.options.createSocket ?? ((url) => new WebSocket(url)))(
      this.options.url,
    );
    this.socket = socket;
    this.connectPromise = new Promise<void>((resolve) => {
      this.settleConnect = resolve;
    });

    this.connectTimer = setTimeout(() => {
      if (!this.isCurrentSocket(socket)) return;
      this.socket = null;
      this.preferSse = true;
      this.finishConnect();
      this.options.onFallback({
        reason: "connect_timeout",
        duringTurn: false,
      });
      socket.close();
    }, WS_CONNECT_TIMEOUT_MS);

    socket.onopen = () => {
      this.clearConnectTimer();
      if (!this.isCurrentSocket(socket)) {
        this.finishConnect();
        socket.close();
        return;
      }
      this.sendFrame({
        token: this.options.token,
        client_timezone: this.options.clientTimezone,
      } satisfies ChatWsAuthFrame);
      this.finishConnect();
    };

    const disconnect = () => {
      this.clearConnectTimer();
      this.clearFirstEventTimer();
      this.finishConnect();
      if (!this.isCurrentSocket(socket)) return;
      const duringTurn = this.turnActive;
      this.socket = null;
      this.turnActive = false;
      this.preferSse = true;
      this.options.onFallback({ reason: "disconnect", duringTurn });
    };

    socket.onclose = disconnect;
    socket.onerror = () => {
      disconnect();
      socket.close();
    };
    socket.onmessage = (event) => {
      if (!this.isCurrentSocket(socket)) return;
      // React Native and DOM WebSocket both expose `data`, but use different
      // concrete event types. String conversion is the narrow shared boundary.
      const payload = parseChatWsPayload(String(event.data));
      if (!payload) return;
      if (WS_TURN_EVENT_TYPES.has(payload.type)) {
        this.clearFirstEventTimer();
      }

      if (payload.type === "error" && payload.message === "Unauthorized") {
        const duringTurn = this.turnActive;
        this.socket = null;
        this.turnActive = false;
        this.preferSse = true;
        this.options.onFallback({
          reason: "unauthorized",
          duringTurn,
          payload,
        });
        socket.close();
        return;
      }

      if (payload.type === "done" || payload.type === "error") {
        this.turnActive = false;
      }
      this.options.onPayload(payload);
    };

    return this.connectPromise;
  }

  sendMessage(frame: Omit<ChatWsMessageFrame, "type">): boolean {
    return this.beginTurn({ type: "message", ...frame });
  }

  sendRegenerate(frame: Omit<ChatWsRegenerateFrame, "type">): boolean {
    return this.beginTurn({ type: "regenerate", ...frame });
  }

  cancel(): void {
    this.clearFirstEventTimer();
    if (this.isOpen()) this.sendFrame({ type: "cancel" });
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.clearConnectTimer();
    this.clearFirstEventTimer();
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
    this.clearFirstEventTimer();
    this.firstEventTimer = setTimeout(() => {
      if (!this.turnActive || !this.socket) return;
      const socket = this.socket;
      this.firstEventTimer = null;
      this.socket = null;
      this.turnActive = false;
      this.preferSse = true;
      this.options.onFallback({
        reason: "first_event_timeout",
        duringTurn: true,
      });
      socket.close();
    }, WS_FIRST_EVENT_TIMEOUT_MS);
    this.sendFrame(frame);
    return true;
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

  private clearFirstEventTimer(): void {
    if (this.firstEventTimer == null) return;
    clearTimeout(this.firstEventTimer);
    this.firstEventTimer = null;
  }

  private finishConnect(): void {
    const settle = this.settleConnect;
    this.settleConnect = null;
    this.connectPromise = null;
    settle?.();
  }
}
