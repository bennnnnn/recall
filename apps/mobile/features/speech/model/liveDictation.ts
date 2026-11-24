import { speechApi, speechLanguageHint, type DictationSessionCredential } from "@/features/speech/api";
import {
  applyTranscriptEvent,
  EMPTY_TRANSCRIPT,
  isEmptyCommitError,
  transcriptSettled,
  transcriptText,
  type DictationTranscript,
} from "@/features/speech/model/dictationTranscript";
import {
  closeRealtimeMicrophone,
  createRealtimePeer,
  debugRealtime,
  loadWebRtc,
  openRealtimeMicrophone,
  webRtcMicConstraints,
} from "@/features/speech/model/realtimePeer";
import { abortError, untilAborted } from "@/lib/api/deadline";
import { meteringLevel } from "@/lib/speech/voiceAudio";

/**
 * Live dictation: the composer mic streams to an OpenAI transcription session over WebRTC,
 * as live talk does, and the words come back on the call's data channel while the user
 * speaks. Recall's API mints the session (one of the day's voice inputs) and opens the call
 * with a secret it keeps (`POST /speech/dictation/session`, `/connect`); no OpenAI key or
 * secret reaches the phone. The stop commits the last words and waits for their final text,
 * about half a second, never a re-transcription of the take.
 *
 * WebRTC needs a dev build: in Expo Go `isLiveDictationAvailable` is false and the composer
 * records a clip and uploads it, as before.
 */

export type LiveDictation = {
  /** The take stops by then: the server hangs up soon after. */
  maxMs: number;
  /** Stop: commit the last words, wait for their final text, hang up. The whole text. */
  finish: () => Promise<string>;
  /** Drop the take and hang up; nothing lands. */
  cancel: () => void;
};

type Handlers = {
  /** The text so far, each time a word arrives or a stretch's final text replaces its words. */
  onText: (text: string) => void;
  /** The mic's level for the waveform, 0 to 1. */
  onLevel: (level: number) => void;
  /** The call failed mid-take; `text` is what was heard, and the take is over. */
  onDropped: (error: Error, text: string) => void;
};

type Peer = ReturnType<typeof createRealtimePeer>;

/** One take's call as its events arrive: the words, and whether the stop's commit has landed. */
type Call = {
  transcript: DictationTranscript;
  connected: boolean;
  closed: boolean;
  commitSent: boolean;
  commitSeen: boolean;
  /** Set while the stop waits for the final text. */
  settle: (() => void) | null;
  drop: (error: Error) => void;
};

// The stop lets audio already on its way arrive before the commit closes the take.
const STOP_TAIL_MS = 200;
// The final text comes about 0.5 s after the commit (measured 2026-11-23); past this the
// words already shown are the take.
const FINAL_WAIT_MS = 2_500;
const LEVEL_POLL_MS = 100;
// The peer closes once the server has hung the call up, or after this at the latest.
const PEER_CLOSE_GRACE_MS = 1_500;

export function isLiveDictationAvailable(): boolean {
  return loadWebRtc() !== null;
}

function logEndFailure(error: unknown): void {
  debugRealtime("dictation-end-failed", error instanceof Error ? error.name : typeof error);
}

/** The call's `audioLevel` (linear, 0 to 1) on the waveform's scale. */
function dictationMeterLevel(audioLevel: number): number {
  if (!(audioLevel > 0)) return meteringLevel(undefined);
  return meteringLevel(20 * Math.log10(Math.min(1, audioLevel)), "peak");
}

/** A data-channel event: the words grow, and the stop's wait ends once its text is final. */
function onCallEvent(call: Call, event: Record<string, unknown>, handlers: Handlers): void {
  if (call.closed) return;
  if (isEmptyCommitError(event)) {
    call.settle?.();
    return;
  }
  if (call.commitSent && event.type === "input_audio_buffer.committed") call.commitSeen = true;
  const next = applyTranscriptEvent(call.transcript, event);
  if (next !== call.transcript) {
    call.transcript = next;
    handlers.onText(transcriptText(next));
  }
  if (call.commitSeen && transcriptSettled(call.transcript)) call.settle?.();
}

/** Mint the session while the offer is made, and connect; a failure gives the voice input back. */
async function connectCall(token: string, peer: Peer, signal: AbortSignal): Promise<DictationSessionCredential> {
  const credential = speechApi.createDictationSession(token, { language: speechLanguageHint() });
  credential.catch(logEndFailure);
  try {
    return await untilAborted(
      (async () => {
        const offerSdp = await peer.createOffer();
        if (signal.aborted) throw abortError();
        const minted = await credential;
        if (signal.aborted) throw abortError();
        await peer.connect(token, minted.call_id, offerSdp, signal, speechApi.connectDictationSession);
        return minted;
      })(),
      signal,
    );
  } catch (error) {
    peer.closeChannel();
    peer.close();
    void credential
      .then(({ call_id: callId }) => speechApi.endDictationSession(token, callId, false))
      .catch(logEndFailure);
    throw error;
  }
}

/** Commit the last words and wait for their final text (or nothing left to commit). */
async function commitAndWait(call: Call, peer: Peer): Promise<void> {
  if (call.closed) return;
  call.commitSent = true;
  peer.send({ type: "input_audio_buffer.commit" });
  await new Promise<void>((resolve) => {
    const deadline = setTimeout(resolve, FINAL_WAIT_MS);
    call.settle = () => {
      clearTimeout(deadline);
      resolve();
    };
  });
}

/**
 * Open the mic and the call. Rejects when it cannot: a refusal from the server keeps its code
 * (the plan, the day's cap), anything else means the call could not be made, and the caller
 * records the clip instead. `signal` cancels a start still connecting.
 */
export async function startLiveDictation(options: {
  token: string;
  signal: AbortSignal;
  handlers: Handlers;
}): Promise<LiveDictation> {
  const { token, signal, handlers } = options;
  const webrtc = loadWebRtc();
  if (!webrtc) throw new Error("webrtc_unavailable");
  const { stream, audioTracks } = await openRealtimeMicrophone(webrtc, webRtcMicConstraints());
  if (signal.aborted) {
    closeRealtimeMicrophone(stream);
    throw abortError();
  }
  const call: Call = {
    transcript: EMPTY_TRANSCRIPT,
    connected: false,
    closed: false,
    commitSent: false,
    commitSeen: false,
    settle: null,
    drop: () => undefined,
  };
  const peer = createRealtimePeer(webrtc, stream, {
    onOpen: () => undefined,
    onMessage: (event) => onCallEvent(call, event, handlers),
    onPeerFailed: (message) => call.drop(new Error(message)),
    onChannelFailed: (message) => call.drop(new Error(message)),
  });
  let session: DictationSessionCredential;
  try {
    session = await connectCall(token, peer, signal);
  } catch (error) {
    call.closed = true;
    throw error;
  }
  call.connected = true;

  const meter = setInterval(() => {
    void peer.micLevel().then((level) => {
      if (level != null && !call.closed) handlers.onLevel(dictationMeterLevel(level));
    });
  }, LEVEL_POLL_MS);
  const hangUp = () => {
    if (call.closed) return;
    call.closed = true;
    clearInterval(meter);
    for (const track of audioTracks) track.enabled = false;
    // The server hangs up before the peer closes: OpenAI confirms a call still connected at
    // once, but one whose phone has left only after about five seconds.
    let peerOpen = true;
    const closePeer = () => {
      if (!peerOpen) return;
      peerOpen = false;
      clearTimeout(grace);
      peer.closeChannel();
      peer.close();
    };
    const grace = setTimeout(closePeer, PEER_CLOSE_GRACE_MS);
    const heard = transcriptText(call.transcript).length > 0;
    void speechApi
      .endDictationSession(token, session.call_id, heard)
      .catch(logEndFailure)
      .finally(closePeer);
  };
  let finishing: Promise<string> | null = null;
  call.drop = (error) => {
    if (!call.connected || call.closed || finishing) return;
    hangUp();
    handlers.onDropped(error, transcriptText(call.transcript));
  };
  const finish = async (): Promise<string> => {
    await new Promise((resolve) => setTimeout(resolve, STOP_TAIL_MS));
    // The commit closes the take: nothing said after the stop goes with it.
    for (const track of audioTracks) track.enabled = false;
    await commitAndWait(call, peer);
    hangUp();
    return transcriptText(call.transcript);
  };
  return {
    maxMs: Math.max(1, session.max_duration_seconds) * 1000,
    finish: () => (finishing ??= finish()),
    cancel: hangUp,
  };
}
