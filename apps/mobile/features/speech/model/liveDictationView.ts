import { useSyncExternalStore } from "react";

/**
 * What the composer's waveform shows of a live dictation: starting (the call connecting),
 * live (the words so far), or finishing (the last words landing). The waveform is its only
 * reader; the words reach the draft through the composer. Kept out of React state so a word
 * arriving redraws the waveform's line, not the chat screen (as the mic level is a shared value).
 */
type LiveDictationPhase = "idle" | "starting" | "live" | "finishing";

type LiveDictationView = { phase: LiveDictationPhase; text: string };

const IDLE: LiveDictationView = { phase: "idle", text: "" };

let view: LiveDictationView = IDLE;
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function snapshot(): LiveDictationView {
  return view;
}

export function showLiveDictation(next: LiveDictationView): void {
  if (next.phase === view.phase && next.text === view.text) return;
  view = next;
  for (const listener of listeners) listener();
}

/** The take stopped: its words stay up while the last of them land. */
export function showLiveDictationFinishing(): void {
  showLiveDictation({ phase: "finishing", text: view.text });
}

export function hideLiveDictation(): void {
  showLiveDictation(IDLE);
}

export function useLiveDictationView(): LiveDictationView {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}
