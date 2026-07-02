import type { AppearancePreference } from "@/lib/appearance";

type Listener = () => void;

let preference: AppearancePreference = "system";
const listeners = new Set<Listener>();

export function getAppearancePreferenceSnapshot(): AppearancePreference {
  return preference;
}

export function setAppearancePreferenceSnapshot(next: AppearancePreference): void {
  if (preference === next) return;
  preference = next;
  listeners.forEach((listener) => listener());
}

export function subscribeAppearancePreference(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Test helper — reset store between cases. */
export function resetAppearanceRuntime(): void {
  preference = "system";
  listeners.clear();
}
