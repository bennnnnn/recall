/**
 * What is being read aloud now, for the small player over the composer: which reply, whether
 * its voice is still being prepared, is playing or is paused, and how far it has got.
 *
 * The reading itself is `pronunciation.ts`. It reports here as it goes, hands over the pause
 * and resume of whatever is playing (a cloud clip's player, or the phone's own voice), and
 * asks `readAloudPaused()` before it takes a clip that stopped for one that finished. Read
 * aloud had only the speaker icon on its reply: no pause, no sign of the seconds it took to
 * fetch the voice, and nothing to stop it once the reply scrolled away.
 */
import { createValueStore } from "@/lib/listenerSet";
import { reportFailure } from "@/lib/sentry";

type ReadAloudPhase = "preparing" | "playing" | "paused";

export type ReadAloud = {
  /** Which reading this is: a reading that ended never clears the one after it. */
  id: number;
  messageId: string;
  phase: ReadAloudPhase;
  /** Seconds heard so far, in ms: the clips' own clocks, or the phone's voice timed below. */
  elapsedMs: number;
  /** The phone's voice is sounding since this time (it reports no clock); null otherwise. */
  playingSince: number | null;
  /** The whole reading's length once its last clip is playing; null until then. */
  totalMs: number | null;
  /** 0 to 1 across the reply's clips; null while the phone's own voice reads (it has no clock). */
  progress: number | null;
  /** The voice playing can pause: every cloud clip, and the phone's own voice on iOS. */
  canPause: boolean;
};

/** What plays now: a clip's player, or the phone's voice (whose calls return promises). */
type PlaybackControls = { pause: () => unknown; resume: () => unknown; canPause: boolean };

export const readAloudSession = createValueStore<ReadAloud | null>(null);
let controls: PlaybackControls | null = null;
/** How the reading stops (pronunciation's stopSpeaking): the player's Stop calls it. */
let stopper: (() => void) | null = null;
let chunk = { index: 0, count: 1 };
let lastId = 0;
/** The finished clips' length, and the one playing (from its status), in ms. */
let heardClipsMs = 0;
let clipMs = 0;

/** A reply starts being read: its player shows at once, while the voice is prepared. */
export function startReadAloud(messageId: string, stop?: () => void): number {
  controls = null;
  stopper = stop ?? null;
  chunk = { index: 0, count: 1 };
  heardClipsMs = 0;
  clipMs = 0;
  lastId += 1;
  readAloudSession.set({
    id: lastId,
    messageId,
    phase: "preparing",
    elapsedMs: 0,
    playingSince: null,
    totalMs: null,
    progress: null,
    canPause: false,
  });
  return lastId;
}

/** Time heard at `now`: what was counted, plus the phone's voice since it started sounding. */
export function readAloudElapsedMs(session: ReadAloud, now: number): number {
  return session.elapsedMs + (session.playingSince === null ? 0 : Math.max(0, now - session.playingSince));
}

/** Reading `id` is over (finished, stopped, failed); with no id, whatever is reading. */
export function endReadAloud(id?: number): void {
  const current = readAloudSession.get();
  if (!current || (id !== undefined && current.id !== id)) return;
  controls = null;
  stopper = null;
  readAloudSession.set(null);
}

/** The player's Stop: the reading stops and the player closes. */
export function stopReadAloud(): void {
  const stop = stopper;
  endReadAloud();
  stop?.();
}

/**
 * A clip finished and its player was released: until the next clip plays there is nothing to
 * pause. Pause in that gap once reached the released player, and said "Paused" over nothing.
 */
export function readAloudClipEnded(): void {
  controls = null;
  heardClipsMs += clipMs;
  clipMs = 0;
  // The wait for the next clip is not heard: the time stops until it plays.
  update({ phase: "preparing", canPause: false, elapsedMs: heardClipsMs });
}

/** Which clip of how many plays next; progress counts the clips before it as heard. */
export function readAloudChunk(index: number, count: number): void {
  chunk = { index, count: Math.max(1, count) };
}

/** Sound started: the player can pause it now. The phone's voice reports no time. */
export function readAloudPlaying(next: PlaybackControls, timed: boolean): void {
  controls = next;
  const current = readAloudSession.get();
  update({
    phase: "playing",
    canPause: next.canPause,
    progress: timed ? chunk.index / chunk.count : null,
    // The phone's voice has no clock: it is timed from when it sounds (across its sentences).
    playingSince: timed ? null : (current?.playingSince ?? Date.now()),
  });
}

/** Where the clip playing has got to, from its player's status. */
export function readAloudClipTime(currentTime: number | undefined, duration: number | undefined): void {
  if (!duration || duration <= 0 || currentTime === undefined) return;
  clipMs = duration * 1000;
  const within = Math.min(1, Math.max(0, currentTime / duration));
  const progress = (chunk.index + within) / chunk.count;
  const elapsedMs = heardClipsMs + Math.min(currentTime, duration) * 1000;
  const last = chunk.index >= chunk.count - 1;
  const current = readAloudSession.get();
  // Status arrives ten times a second: redraw for a 1% move or another second shown.
  const sameSecond = current && Math.floor(current.elapsedMs / 1000) === Math.floor(elapsedMs / 1000);
  const sameProgress = current?.progress != null && Math.abs(current.progress - progress) < 0.01;
  if (sameSecond && sameProgress && (!last || current?.totalMs !== null)) return;
  update({ progress, elapsedMs, totalMs: last ? heardClipsMs + clipMs : null });
}

export function readAloudPaused(): boolean {
  return readAloudSession.get()?.phase === "paused";
}

export function pauseReadAloud(): void {
  const current = readAloudSession.get();
  if (!controls?.canPause || current?.phase !== "playing") return;
  if (!control(controls.pause)) return;
  update({ phase: "paused", elapsedMs: readAloudElapsedMs(current, Date.now()), playingSince: null });
}

export function resumeReadAloud(): void {
  const current = readAloudSession.get();
  if (!controls || !current || current.phase !== "paused") return;
  if (!control(controls.resume)) return;
  // A clip's own clock goes on by itself; the phone's voice is timed again from now.
  update({ phase: "playing", playingSince: current.progress === null ? Date.now() : null });
}

function reportControlFailed(error: unknown): void {
  reportFailure("read_aloud_control", error);
}

/** Run a pause or resume; one that fails is reported and never thrown into the tap. */
function control(action: () => unknown): boolean {
  try {
    const result = action();
    if (result instanceof Promise) result.catch(reportControlFailed);
    return true;
  } catch (error) {
    reportControlFailed(error);
    return false;
  }
}

function update(patch: Partial<ReadAloud>): void {
  const current = readAloudSession.get();
  if (current) readAloudSession.set({ ...current, ...patch });
}
