import { isAbortError } from "@/lib/api/abort";
import { reportFailure } from "@/lib/sentry";
import { VOICE_MAX_RECORDING_MS } from "@/lib/speech/voiceAudio";
import { startLiveDictation, type LiveDictation } from "@/features/speech/model/liveDictation";
import {
  hideLiveDictation,
  showLiveDictation,
  showLiveDictationFinishing,
} from "@/features/speech/model/liveDictationView";
import { liveTalkErrorGate } from "@/features/speech/model/liveTalkLogic";
import { liveDictationFallsBack, liveDictationUnavailable } from "@/features/speech/model/voiceRefusal";

/** What a live take tells the composer mic (`useVoiceInput`) it holds. */
type LiveTakeHost = {
  token: () => string | null;
  setRecording: (on: boolean) => void;
  setTranscribing: (on: boolean) => void;
  setLevel: (level: number) => void;
  onLiveText: (text: string) => void;
  onTranscript: (text: string) => void;
  /** Says a dictation message by its i18n key. */
  say: (key: string) => void;
  /** A refusal the upload would meet too (the plan, the day's cap), said as it always was. */
  sayRefusal: (error: unknown) => void;
  /** The phone refused the microphone: only Settings can turn it back on. */
  micDenied: () => void;
};

/** How a start ended: the take runs, the clip is recorded instead, or neither. */
type LiveTakeStart = "live" | "fallback" | "stopped";

export type LiveTake = {
  start: () => Promise<LiveTakeStart>;
  /** The stop: the last words land; while the call still connects, the take is dropped. */
  finish: () => Promise<string | null>;
  cancel: () => void;
  /** A take connecting or running. */
  busy: () => boolean;
};

const METER_REST = 0.12;

/** The take in progress. `gen` moves on at every start, stop and cancel. */
type TakeState = {
  gen: number;
  live: LiveDictation | null;
  starting: AbortController | null;
  timer: ReturnType<typeof setTimeout> | null;
};

function clearTimer(state: TakeState): void {
  if (state.timer != null) clearTimeout(state.timer);
  state.timer = null;
}

/** The call dropped mid-take: what was heard lands, and the take is over. */
function onDropped(host: LiveTakeHost, state: TakeState, own: number, error: Error, text: string): void {
  if (own !== state.gen) return;
  reportFailure("live_dictation", error);
  state.live = null;
  clearTimer(state);
  host.setRecording(false);
  host.setLevel(METER_REST);
  hideLiveDictation();
  if (text) host.onTranscript(text);
  else host.say("chat.voice_transcribe_failed");
}

function takeHandlers(host: LiveTakeHost, state: TakeState, own: number) {
  return {
    onText: (text: string) => {
      if (own !== state.gen) return;
      showLiveDictation({ phase: state.live ? "live" : "finishing", text });
      host.onLiveText(text);
    },
    onLevel: (level: number) => {
      if (own === state.gen && state.live) host.setLevel(level);
    },
    onDropped: (error: Error, text: string) => onDropped(host, state, own, error, text),
  };
}

/** A start that failed: the clip is recorded instead, or the refusal is said. */
function startFailed(host: LiveTakeHost, error: unknown): LiveTakeStart {
  hideLiveDictation();
  if (liveTalkErrorGate(error) === "mic_permission") {
    host.setRecording(false);
    host.micDenied();
    return "stopped";
  }
  if (liveDictationFallsBack(error)) {
    if (!liveDictationUnavailable(error)) reportFailure("live_dictation", error);
    return "fallback";
  }
  host.setRecording(false);
  host.sayRefusal(error);
  return "stopped";
}

/** The stop of a running take: its last words land within about a second. */
async function finishTake(host: LiveTakeHost, state: TakeState, take: LiveDictation): Promise<string | null> {
  const own = state.gen;
  state.live = null;
  clearTimer(state);
  host.setRecording(false);
  host.setTranscribing(true);
  host.setLevel(METER_REST);
  showLiveDictationFinishing();
  try {
    const text = await take.finish();
    if (own !== state.gen) return null;
    if (!text) {
      host.say("chat.voice_transcribe_empty");
      return null;
    }
    host.onTranscript(text);
    return text;
  } finally {
    if (own === state.gen) {
      host.setTranscribing(false);
      hideLiveDictation();
    }
  }
}

/**
 * One live take at a time for the composer mic: start it, show its words as they arrive, and
 * land the whole text at the stop, at the time limit, or when the call drops. A call that
 * answers after a stop or cancel lands nothing.
 */
export function createLiveTake(host: LiveTakeHost): LiveTake {
  const state: TakeState = { gen: 0, live: null, starting: null, timer: null };

  const cancel = () => {
    state.gen += 1;
    state.starting?.abort();
    state.starting = null;
    state.live?.cancel();
    state.live = null;
    clearTimer(state);
    hideLiveDictation();
  };

  const finish = async (): Promise<string | null> => {
    const take = state.live;
    if (take) return finishTake(host, state, take);
    // Stopped while the call was still connecting: nothing was heard yet.
    cancel();
    host.setRecording(false);
    return null;
  };

  const start = async (): Promise<LiveTakeStart> => {
    const token = host.token();
    if (!token) return "stopped";
    state.gen += 1;
    const own = state.gen;
    const controller = new AbortController();
    state.starting = controller;
    // The waveform shows at once and says it is starting: the first words wait for the call.
    host.setRecording(true);
    showLiveDictation({ phase: "starting", text: "" });
    try {
      const handlers = takeHandlers(host, state, own);
      const take = await startLiveDictation({ token, signal: controller.signal, handlers });
      if (own !== state.gen) {
        take.cancel();
        return "stopped";
      }
      state.live = take;
      showLiveDictation({ phase: "live", text: "" });
      state.timer = setTimeout(() => void finish(), Math.min(VOICE_MAX_RECORDING_MS, take.maxMs));
      return "live";
    } catch (error) {
      if (own !== state.gen || isAbortError(error)) return "stopped";
      return startFailed(host, error);
    } finally {
      if (state.starting === controller) state.starting = null;
    }
  };

  return { start, finish, cancel, busy: () => state.live != null || state.starting != null };
}
