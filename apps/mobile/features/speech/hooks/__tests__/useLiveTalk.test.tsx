import React from "react";
import { BackHandler, Linking } from "react-native";
import { act, render } from "@testing-library/react-native";

import { useLiveTalk } from "@/features/speech/hooks/useLiveTalk";
import { api } from "@/lib/api";
import type { Message } from "@/lib/api/types";
import { ApiRequestError } from "@/lib/api/errorBody";
import { readAloudSession, startReadAloud } from "@/features/speech/model/readAloudSession";
import { createRealtimeVoiceSession } from "@/features/speech/model/realtimeVoice";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import { confirmDialog } from "@/ui/overlay/dialogs";

let mockDrawerOpen = false;
const mockDrawerControls = { open: jest.fn(), close: jest.fn(), isOpenNow: () => mockDrawerOpen };
jest.mock("@/contexts/DrawerContext", () => ({ useDrawerControls: () => mockDrawerControls }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/lib/reportRecoverableError", () => ({ reportRecoverableError: jest.fn() }));
jest.mock("@/ui/overlay/dialogs", () => ({ confirmDialog: jest.fn(async () => true) }));
jest.mock("@/features/speech/model/liveTalkSfx", () => ({ playLiveTalkCue: jest.fn(async () => undefined) }));
jest.mock("@/features/speech/model/realtimeVoice", () => ({
  createRealtimeVoiceSession: jest.fn(),
  isRealtimeVoiceAvailable: () => true,
}));
jest.mock("@/lib/api", () => ({
  api: {
    liveTalkStatus: jest.fn(async () => ({
      enabled: true,
      entitled: true,
      remaining: 30,
      limit: 60,
      remaining_seconds: 1800,
      min_session_seconds: 60,
    })),
    endRealtimeSession: jest.fn(async () => ({})),
    persistRealtimeLiveTalkTurn: jest.fn(),
  },
}));

let live!: ReturnType<typeof useLiveTalk>;
const onUpgrade = jest.fn();

function Probe() {
  const value = useLiveTalk({
    token: "tok",
    chatId: "chat-1",
    ensureChatId: async () => "chat-1",
    editThread: jest.fn(),
    isOffline: false,
    onUpgrade,
    onScrollToLatest: jest.fn(),
    newMessageCountRef: { current: 0 },
    onFirstReply: jest.fn(),
    t: (key: string) => key,
  });
  React.useLayoutEffect(() => {
    live = value;
  });
  return null;
}

/** Open a call; returns what the realtime session says to the hook. */
async function openCall(): Promise<(event: { type: string; [key: string]: unknown }) => void> {
  let emit!: (event: { type: string; [key: string]: unknown }) => void;
  (createRealtimeVoiceSession as jest.Mock).mockImplementationOnce(async ({ onEvent }) => {
    emit = onEvent;
    return { callId: "call-1", maxDurationSeconds: 600, setMuted: jest.fn(), cancelResponse: jest.fn(), close: jest.fn() };
  });
  await render(<Probe />);
  await act(async () => {
    await live.open();
  });
  expect(live.visible).toBe(true);
  return emit;
}

describe("useLiveTalk microphone denial (F8.8)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("asks for the microphone with Open Settings instead of the generic unavailable", async () => {
    const openSettings = jest.spyOn(Linking, "openSettings").mockResolvedValue(undefined);
    (createRealtimeVoiceSession as jest.Mock).mockRejectedValueOnce({
      name: "SecurityError",
      message: "Permission denied.",
    });
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(confirmDialog).toHaveBeenCalledWith({
      title: "chat.live_talk_mic_permission_title",
      message: "chat.live_talk_mic_permission_body",
      cancelLabel: "common.cancel",
      confirmLabel: "chat.location_open_settings",
    });
    expect(reportRecoverableError).not.toHaveBeenCalled();
    expect(openSettings).toHaveBeenCalledTimes(1);
    expect(live.visible).toBe(false);
    openSettings.mockRestore();
  });

  it("still says unavailable when WebRTC itself is missing", async () => {
    (createRealtimeVoiceSession as jest.Mock).mockRejectedValueOnce(new Error("webrtc_unavailable"));
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(confirmDialog).not.toHaveBeenCalled();
    expect(reportRecoverableError).toHaveBeenCalledWith(null, "chat.live_talk_unavailable_body");
  });

  // A microphone that gave no audio said "update the app", as a build without WebRTC does.
  it("says the microphone, not the app, when the microphone gave no audio", async () => {
    (createRealtimeVoiceSession as jest.Mock).mockRejectedValueOnce(new Error("microphone_unavailable"));
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(confirmDialog).not.toHaveBeenCalled();
    expect(jest.mocked(reportRecoverableError).mock.calls).toEqual([[null, "chat.live_talk_mic_unavailable"]]);
    expect(live.visible).toBe(false);
  });

  // Every 503 said "Live talk isn't set up on this server yet", a Redis outage included.
  it.each([
    [{ code: "unavailable", message: "Service temporarily unavailable. Please retry shortly." }, "common.service_unavailable"],
    [{ code: "not_configured", message: "Realtime voice is not configured" }, "chat.live_talk_not_configured"],
  ])("words a 503 by its code: %j", async (detail, line) => {
    jest.mocked(api.liveTalkStatus).mockRejectedValueOnce(new ApiRequestError(503, JSON.stringify({ detail })));
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(reportRecoverableError).toHaveBeenCalledWith(null, line);
    expect(createRealtimeVoiceSession).not.toHaveBeenCalled();
  });

  // Every 429 said "You've used this month's live talk minutes"; a 502 from the
  // realtime provider said "Update the app".
  it.each([
    [429, { code: "live_talk_minutes_used", message: "You've used this month's live talk minutes." }, "chat.live_talk_limit_body"],
    [429, { code: "speech_rate_limited", message: "Too many live talk requests." }, "chat.live_talk_rate_limited"],
    [429, { code: "voice_spend_cap", message: "Voice is temporarily unavailable." }, "chat.live_talk_paused"],
    [502, { code: "upstream_failed", message: "Could not start realtime voice" }, "chat.live_talk_connect_failed"],
  ])("words a refused start (%i) by its code: %j", async (status, detail, line) => {
    (createRealtimeVoiceSession as jest.Mock).mockRejectedValueOnce(
      new ApiRequestError(status, JSON.stringify({ detail })),
    );
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(reportRecoverableError).toHaveBeenCalledWith(null, line);
    expect(live.visible).toBe(false);
  });

  // Every 403 opened the paywall: consent_required did too, on top of the consent step
  // the API client opens for it.
  it.each([
    [{ code: "not_in_plan", message: "Live talk isn't part of your plan." }, 1],
    [{ code: "consent_required", message: "Agree to how Recall uses outside AI services to continue." }, 0],
  ])("opens the paywall only for not_in_plan: %j", async (detail, paywalls) => {
    (createRealtimeVoiceSession as jest.Mock).mockRejectedValueOnce(
      new ApiRequestError(403, JSON.stringify({ detail })),
    );
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(onUpgrade).toHaveBeenCalledTimes(paywalls);
    expect(reportRecoverableError).not.toHaveBeenCalled();
    expect(live.visible).toBe(false);
  });

  it("words the API's own request limit, which names no code, as too many attempts", async () => {
    jest.mocked(api.liveTalkStatus).mockRejectedValueOnce(
      new ApiRequestError(429, JSON.stringify({ detail: "Too many requests. Please slow down." })),
    );
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(reportRecoverableError).toHaveBeenCalledWith(null, "chat.live_talk_rate_limited");
    expect(createRealtimeVoiceSession).not.toHaveBeenCalled();
  });

  it("says live talk is off, not that the app is old, when the server switched it off", async () => {
    jest.mocked(api.liveTalkStatus).mockResolvedValueOnce({ enabled: false, entitled: false, remaining: 0, limit: 0 });
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(reportRecoverableError).toHaveBeenCalledWith(null, "chat.live_talk_off");
    expect(createRealtimeVoiceSession).not.toHaveBeenCalled();
  });

  // A save never gets `live_talk_minutes_used`, yet each of its 429s said the month was used.
  it.each([
    [{ code: "rate_limited", message: "Too many live talk requests." }, "chat.live_talk_rate_limited"],
    [{ code: "voice_spend_cap", message: "Voice is temporarily unavailable." }, "chat.live_talk_paused"],
    [{ code: "live_talk_saves_used", message: "This live talk call can't save more turns." }, "chat.live_talk_saves_used"],
  ])("ends the call on a refused save in its own words: %j", async (detail, line) => {
    let emit!: (event: { type: string; [key: string]: unknown }) => void;
    (createRealtimeVoiceSession as jest.Mock).mockImplementationOnce(async ({ onEvent }) => {
      emit = onEvent;
      return { callId: "call-1", maxDurationSeconds: 600, setMuted: jest.fn(), cancelResponse: jest.fn(), close: jest.fn() };
    });
    jest.mocked(api.persistRealtimeLiveTalkTurn).mockRejectedValueOnce(
      new ApiRequestError(429, JSON.stringify({ detail })),
    );
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });
    expect(live.visible).toBe(true);

    await act(async () => {
      emit({ type: "speech_started", turnId: "turn-1" });
      emit({ type: "user_transcript", text: "hello" });
      // The next utterance saves the last one.
      emit({ type: "speech_started", turnId: "turn-2" });
    });

    expect(api.persistRealtimeLiveTalkTurn).toHaveBeenCalledTimes(1);
    expect(reportRecoverableError).toHaveBeenCalledWith(null, line);
    expect(reportRecoverableError).not.toHaveBeenCalledWith(null, "chat.live_talk_limit_body");
    expect(live.visible).toBe(false);
  });

  // A save the plan or the session no longer allowed showed the server's English
  // ("Realtime session is not active") and left the call, and the provider, running.
  it.each([
    [{ code: "not_in_plan", message: "Live talk isn't part of your plan." }, null],
    [{ code: "live_talk_session_ended", message: "Realtime session is not active" }, "chat.live_talk_session_ended"],
  ])("ends the call once on a save the plan or session no longer allows: %j", async (detail, line) => {
    const emit = await openCall();
    jest.mocked(api.persistRealtimeLiveTalkTurn).mockRejectedValue(
      new ApiRequestError(403, JSON.stringify({ detail })),
    );

    await act(async () => {
      emit({ type: "speech_started", turnId: "turn-1" });
      emit({ type: "user_transcript", text: "hello" });
      emit({ type: "speech_started", turnId: "turn-2" });
      // Heard before the refusal lands: the hang-up saves it, and is refused the same way.
      emit({ type: "user_transcript", text: "are you there" });
    });

    expect(api.persistRealtimeLiveTalkTurn).toHaveBeenCalledTimes(2);
    expect(live.visible).toBe(false);
    expect(onUpgrade).toHaveBeenCalledTimes(line ? 0 : 1);
    expect(jest.mocked(reportRecoverableError).mock.calls).toEqual(line ? [[null, line]] : []);
    jest.mocked(api.persistRealtimeLiveTalkTurn).mockReset();
  });

  it.each([
    [new ApiRequestError(404, JSON.stringify({ detail: { code: "not_found", message: "Chat not found" } })),
      "chat.live_talk_save_failed"],
    [new ApiRequestError(500, "Internal Server Error"), "chat.live_talk_save_failed"],
    [new ApiRequestError(503, JSON.stringify({ detail: { code: "unavailable", message: "Service temporarily unavailable." } })),
      "common.service_unavailable"],
  ])("words any other refused save in the phone's language, and keeps the call: %s", async (error, line) => {
    const emit = await openCall();
    jest.mocked(api.persistRealtimeLiveTalkTurn).mockRejectedValueOnce(error);

    await act(async () => {
      emit({ type: "speech_started", turnId: "turn-1" });
      emit({ type: "user_transcript", text: "hello" });
      emit({ type: "speech_started", turnId: "turn-2" });
    });

    expect(reportRecoverableError).toHaveBeenCalledWith(null, line);
    expect(live.visible).toBe(true);
  });

  // Both showed the provider's English.
  it.each([
    [{ type: "error", message: "Realtime voice data channel failed", fatal: true }, "chat.live_talk_connect_failed", false],
    [{ type: "error", message: "Conversation already has an active response" }, "chat.error_generic", true],
  ])("words an error during a call in the phone's language: %j", async (event, line, stillOpen) => {
    const emit = await openCall();

    await act(async () => {
      emit(event);
    });

    expect(jest.mocked(reportRecoverableError).mock.calls).toEqual([[null, line]]);
    expect(live.visible).toBe(stillOpen);
  });

  it("moves the face only while the reply's voice plays", async () => {
    // Hanging up saves the turn so far.
    jest.mocked(api.persistRealtimeLiveTalkTurn).mockResolvedValueOnce(null as never);
    const emit = await openCall();
    expect(live.voicePlaying).toBe(false);

    await act(async () => {
      emit({ type: "assistant_transcript", text: "Hi", final: false });
    });
    // The words arrived; the voice has not started yet.
    expect(live.voicePlaying).toBe(false);
    await act(async () => {
      emit({ type: "output_audio", playing: true });
    });
    expect(live.voicePlaying).toBe(true);
    await act(async () => {
      emit({ type: "output_audio", playing: false });
    });
    expect(live.voicePlaying).toBe(false);

    await act(async () => {
      emit({ type: "output_audio", playing: true });
    });
    await act(async () => {
      live.close();
    });
    expect(live.voicePlaying).toBe(false);
  });

  // Tapping the composer ended the call: its focus, attach and send all called a
  // "yield" that hung up. The composer is gone during a call, and so is that path.
  it("offers nothing that ends the call but close, and muting keeps it up", async () => {
    await openCall();
    expect(Object.keys(live)).not.toContain("yieldToComposer");
    await act(async () => {
      live.toggleMute();
    });
    expect(live.muted).toBe(true);
    expect(live.visible).toBe(true);
    await act(async () => {
      live.close();
    });
    expect(live.visible).toBe(false);
  });

  it("leaves Back to an open drawer, reading the drawer when Back is pressed", async () => {
    const backHandlers: (() => boolean | null | undefined)[] = [];
    const addListener = jest
      .spyOn(BackHandler, "addEventListener")
      .mockImplementation((_event, handler) => {
        backHandlers.push(() => handler({} as never));
        return { remove: jest.fn() };
      });
    (createRealtimeVoiceSession as jest.Mock).mockResolvedValueOnce({
      callId: null,
      maxDurationSeconds: null,
      setMuted: jest.fn(),
      cancelResponse: jest.fn(),
      close: jest.fn(),
    });
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });
    expect(live.visible).toBe(true);
    const back = backHandlers.at(-1)!;

    // The drawer opened after Live Talk did: Back closes the drawer, not Live Talk.
    mockDrawerOpen = true;
    expect(back()).toBe(false);
    expect(live.visible).toBe(true);

    mockDrawerOpen = false;
    await act(async () => {
      expect(back()).toBe(true);
    });
    expect(live.visible).toBe(false);
    addListener.mockRestore();
  });
});

describe("useLiveTalk hang-up while the call connects", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("aborts the connect at once, so its route, mic and minutes go back without waiting for it", async () => {
    let connecting!: AbortSignal;
    (createRealtimeVoiceSession as jest.Mock).mockImplementationOnce(
      ({ signal }: { signal: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          connecting = signal;
          signal.addEventListener("abort", () => reject(Object.assign(new Error("Request canceled"), { name: "AbortError" })));
        }),
    );
    await render(<Probe />);
    let opening!: Promise<void>;
    await act(async () => {
      opening = live.open();
    });
    expect(connecting.aborted).toBe(false);

    await act(async () => {
      live.close();
      await opening;
    });

    expect(connecting.aborted).toBe(true);
    expect(live.visible).toBe(false);
    // A hang-up is no failure: nothing is said about it.
    expect(reportRecoverableError).not.toHaveBeenCalled();
    expect(confirmDialog).not.toHaveBeenCalled();
  });
});

describe("useLiveTalk when the phone takes the call's audio", () => {
  function callSession() {
    return { callId: "call-1", maxDurationSeconds: 600, setMuted: jest.fn(), cancelResponse: jest.fn(), close: jest.fn() };
  }

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // A phone call rang under live talk: the voice talked over the ringtone, the open mic could
  // start a reply, and a call answered with the app open kept charging minutes.
  it("hangs up as the user's hang-up does, once, saying why", async () => {
    jest.mocked(api.persistRealtimeLiveTalkTurn).mockResolvedValueOnce(null as never);
    const session = callSession();
    let emit!: (event: { type: string; [key: string]: unknown }) => void;
    (createRealtimeVoiceSession as jest.Mock).mockImplementationOnce(async ({ onEvent }) => {
      emit = onEvent;
      return session;
    });
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    await act(async () => {
      emit({ type: "speech_started", turnId: "turn-1" });
      emit({ type: "user_transcript", text: "what time is it" });
      emit({ type: "interrupted" });
    });
    await act(async () => {
      live.close();
    });

    expect(live.visible).toBe(false);
    expect(jest.mocked(reportRecoverableError).mock.calls).toEqual([[null, "chat.live_talk_interrupted"]]);
    // The turn heard so far is saved, and the server's session ends once.
    expect(api.persistRealtimeLiveTalkTurn).toHaveBeenCalledWith("tok", expect.objectContaining({
      callId: "call-1", userText: "what time is it",
    }));
    expect(session.close).toHaveBeenCalledTimes(1);
    expect(jest.mocked(api.endRealtimeSession).mock.calls).toEqual([["tok", "call-1"]]);
  });

  it("hangs up a call that is still connecting, saying why", async () => {
    let connecting!: AbortSignal;
    (createRealtimeVoiceSession as jest.Mock).mockImplementationOnce(
      ({ onEvent, signal }: { onEvent: (event: { type: string }) => void; signal: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          connecting = signal;
          signal.addEventListener("abort", () => reject(Object.assign(new Error("Request canceled"), { name: "AbortError" })));
          onEvent({ type: "interrupted" });
        }),
    );
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(connecting.aborted).toBe(true);
    expect(live.visible).toBe(false);
    expect(jest.mocked(reportRecoverableError).mock.calls).toEqual([[null, "chat.live_talk_interrupted"]]);
    // No call id yet: the session's own release gives the minted minutes back.
    expect(api.endRealtimeSession).not.toHaveBeenCalled();
  });

  it("says the phone is on a call when Android refused the call its audio", async () => {
    (createRealtimeVoiceSession as jest.Mock).mockRejectedValueOnce(new Error("phone_busy"));
    await render(<Probe />);
    await act(async () => {
      await live.open();
    });

    expect(jest.mocked(reportRecoverableError).mock.calls).toEqual([[null, "chat.live_talk_phone_busy"]]);
    expect(live.visible).toBe(false);
  });

  it("ends a call that connected after its hang-up once, however often it is closed", async () => {
    const session = callSession();
    let connected!: (value: ReturnType<typeof callSession>) => void;
    (createRealtimeVoiceSession as jest.Mock).mockReturnValueOnce(
      new Promise((resolve) => {
        connected = resolve;
      }),
    );
    await render(<Probe />);
    let opening!: Promise<void>;
    await act(async () => {
      opening = live.open();
    });

    await act(async () => {
      live.close();
      live.close();
    });
    await act(async () => {
      connected(session);
      await opening;
    });
    await act(async () => {
      live.close();
    });

    expect(session.close).toHaveBeenCalledTimes(1);
    expect(jest.mocked(api.endRealtimeSession).mock.calls).toEqual([["tok", "call-1"]]);
  });

  // A reply read aloud went on into the call: when its clip failed it fell back to the phone's
  // voice, which reset the audio mode, and the call's voice left its route.
  it("stops a reply read aloud before the call takes the audio", async () => {
    const stopReading = jest.fn();
    startReadAloud("message-1", stopReading);
    await openCall();

    expect(stopReading).toHaveBeenCalledTimes(1);
    expect(readAloudSession.get()).toBeNull();
    expect(stopReading.mock.invocationCallOrder[0]).toBeLessThan(
      jest.mocked(createRealtimeVoiceSession).mock.invocationCallOrder[0]!,
    );
  });
});

describe("useLiveTalk's turns, mute and limits", () => {
  let thread: Message[] = [];
  let ensureChat: () => Promise<string | null> = async () => "chat-1";
  let maxDurationSeconds = 600;

  function ThreadProbe() {
    const value = useLiveTalk({
      token: "tok",
      chatId: "chat-1",
      ensureChatId: () => ensureChat(),
      editThread: (update) => {
        thread = typeof update === "function" ? update(thread) : update;
      },
      isOffline: false,
      onUpgrade,
      onScrollToLatest: jest.fn(),
      newMessageCountRef: { current: 0 },
      onFirstReply: jest.fn(),
      t: (key: string) => key,
    });
    React.useLayoutEffect(() => {
      live = value;
    });
    return null;
  }

  async function openThreadCall(): Promise<(event: { type: string; [key: string]: unknown }) => void> {
    let emit!: (event: { type: string; [key: string]: unknown }) => void;
    (createRealtimeVoiceSession as jest.Mock).mockImplementationOnce(async ({ onEvent }) => {
      emit = onEvent;
      return { callId: "call-1", maxDurationSeconds, setMuted: jest.fn(), cancelResponse: jest.fn(), close: jest.fn() };
    });
    await render(<ThreadProbe />);
    await act(async () => {
      await live.open();
    });
    expect(live.visible).toBe(true);
    return emit;
  }

  beforeEach(() => {
    jest.clearAllMocks();
    thread = [];
    ensureChat = async () => "chat-1";
    maxDurationSeconds = 600;
  });

  // The line is transcribed beside the reply: it showed under the reply, and a turn saved
  // before it came kept no line (the server keeps no reply without one).
  it("shows a line that lands after its reply above it, and saves the two as one turn", async () => {
    jest.mocked(api.persistRealtimeLiveTalkTurn).mockResolvedValueOnce(undefined);
    const emit = await openThreadCall();
    await act(async () => {
      emit({ type: "speech_started", turnId: "u1" });
      emit({ type: "speech_stopped", replying: true });
      emit({ type: "response_started" });
      emit({ type: "assistant_transcript", text: "Paris.", final: true });
      emit({ type: "response_done" });
    });
    expect(api.persistRealtimeLiveTalkTurn).not.toHaveBeenCalled();

    await act(async () => {
      emit({ type: "user_transcript", text: "What is the capital of France?", turnId: "u1" });
    });

    expect(thread.map((row) => [row.role, row.content])).toEqual([
      ["user", "What is the capital of France?"],
      ["assistant", "Paris."],
    ]);
    expect(jest.mocked(api.persistRealtimeLiveTalkTurn).mock.calls).toEqual([["tok", {
      chatId: "chat-1",
      callId: "call-1",
      userText: "What is the capital of France?",
      assistantText: "Paris.",
      turnId: "u1",
    }]]);
  });

  // Muted mid-sentence, no reply is asked for: the face waited in "thinking" for good.
  it.each([
    [true, "thinking"],
    [false, "recording"],
  ])("waits for a reply only when one was asked for (replying: %s)", async (replying, phase) => {
    const emit = await openThreadCall();
    await act(async () => {
      emit({ type: "speech_started", turnId: "u1" });
      emit({ type: "speech_stopped", replying });
    });
    expect(live.phase).toBe(phase);
  });

  // The call hung up at its time limit with no word.
  it.each([
    [1800, "chat.live_talk_time_up"],
    [60, "chat.live_talk_limit_body"],
  ])("hangs up at the call's time limit and says why (%i s left when it began)", async (secondsLeft, line) => {
    jest.mocked(api.liveTalkStatus).mockResolvedValueOnce({
      enabled: true,
      entitled: true,
      remaining: Math.floor(secondsLeft / 60),
      limit: 60,
      remaining_seconds: secondsLeft,
      min_session_seconds: 60,
    });
    maxDurationSeconds = 0.05;
    await openThreadCall();
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 80));
    });
    expect(live.visible).toBe(false);
    expect(jest.mocked(reportRecoverableError).mock.calls).toEqual([[null, line]]);
  });

  // It ran, spending minutes, with nowhere to save a turn and nothing said.
  it("starts no call, and says why, when no chat can be made to save it to", async () => {
    ensureChat = async () => null;
    await render(<ThreadProbe />);
    await act(async () => {
      await live.open();
    });
    expect(createRealtimeVoiceSession).not.toHaveBeenCalled();
    expect(live.visible).toBe(false);
    expect(jest.mocked(reportRecoverableError).mock.calls).toEqual([[null, "chat.live_talk_no_chat"]]);
  });
});
