import { DEFAULT_ACCENT, type AccentPreference } from "@/lib/accent";

type Listener = () => void;

let accent: AccentPreference = DEFAULT_ACCENT;
const listeners = new Set<Listener>();

export function getAccentSnapshot(): AccentPreference {
  return accent;
}

export function setAccentSnapshot(next: AccentPreference): void {
  if (accent === next) return;
  accent = next;
  listeners.forEach((listener) => listener());
}

export function subscribeAccent(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Test helper — reset store between cases. */
export function resetAccentRuntime(): void {
  accent = DEFAULT_ACCENT;
  listeners.clear();
}
