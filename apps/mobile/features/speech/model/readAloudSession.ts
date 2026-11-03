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
import { markdownToSpeechText } from "@/lib/markdown/plain";

export type ReadAloudPhase = "preparing" | "playing" | "paused";

export type ReadAloud = {
  /** Which reading this is: a reading that ended never clears the one after it. */
  id: number;
  messageId: string;
  /** The reply's opening words, so the player says what it is reading. */
  preview: string;
  phase: ReadAloudPhase;
  /** 0 to 1 across the reply's clips; null while the phone's own voice reads (it has no clock). */
  progress: number | null;
  /** The voice playing can pause: every cloud clip, and the phone's own voice on iOS. */
  canPause: boolean;
};

type PlaybackControls = { pause: () => void; resume: () => void; canPause: boolean };

const PREVIEW_CHARS = 80;

export const readAloudSession = createValueStore<ReadAloud | null>(null);
let controls: PlaybackControls | null = null;
let chunk = { index: 0, count: 1 };
let lastId = 0;

/** A reply starts being read: its player shows at once, while the voice is prepared. */
export function startReadAloud(messageId: string, text: string): number {
  controls = null;
  chunk = { index: 0, count: 1 };
  lastId += 1;
  readAloudSession.set({
    id: lastId,
    messageId,
    preview: previewOf(text),
    phase: "preparing",
    progress: null,
    canPause: false,
  });
  return lastId;
}

/** Reading `id` is over (finished, stopped, failed); with no id, whatever is reading. */
export function endReadAloud(id?: number): void {
  const current = readAloudSession.get();
  if (!current || (id !== undefined && current.id !== id)) return;
  controls = null;
  readAloudSession.set(null);
}

/** Which clip of how many plays next; progress counts the clips before it as heard. */
export function readAloudChunk(index: number, count: number): void {
  chunk = { index, count: Math.max(1, count) };
}

/** Sound started: the player can pause it now. The phone's voice reports no time. */
export function readAloudPlaying(next: PlaybackControls, timed: boolean): void {
  controls = next;
  update({
    phase: "playing",
    canPause: next.canPause,
    progress: timed ? chunk.index / chunk.count : null,
  });
}

/** Where the clip playing has got to, from its player's status. */
export function readAloudClipTime(currentTime: number | undefined, duration: number | undefined): void {
  if (!duration || duration <= 0 || currentTime === undefined) return;
  const within = Math.min(1, Math.max(0, currentTime / duration));
  const progress = (chunk.index + within) / chunk.count;
  const current = readAloudSession.get();
  // Status arrives ten times a second; a change under 1% redraws nothing anyone sees.
  if (current?.progress != null && Math.abs(current.progress - progress) < 0.01) return;
  update({ progress });
}

export function readAloudPaused(): boolean {
  return readAloudSession.get()?.phase === "paused";
}

export function pauseReadAloud(): void {
  const current = readAloudSession.get();
  if (!controls?.canPause || current?.phase !== "playing") return;
  controls.pause();
  update({ phase: "paused" });
}

export function resumeReadAloud(): void {
  if (!controls || !readAloudPaused()) return;
  controls.resume();
  update({ phase: "playing" });
}

function update(patch: Partial<ReadAloud>): void {
  const current = readAloudSession.get();
  if (current) readAloudSession.set({ ...current, ...patch });
}

function previewOf(text: string): string {
  const line = markdownToSpeechText(text).replace(/\s+/g, " ").trim();
  return line.length > PREVIEW_CHARS ? `${line.slice(0, PREVIEW_CHARS).trimEnd()}…` : line;
}
