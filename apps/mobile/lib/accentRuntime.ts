import { createContext, createElement, type ReactNode, useContext, useSyncExternalStore } from "react";

import { DEFAULT_ACCENT, type AccentPreference } from "@/lib/accent";
import { createValueStore } from "@/lib/listenerSet";

const accent = createValueStore<AccentPreference>(DEFAULT_ACCENT);

function getAccentSnapshot(): AccentPreference {
  return accent.get();
}

export function setAccentSnapshot(next: AccentPreference): void {
  accent.set(next);
}

function subscribeAccent(listener: () => void): () => void {
  return accent.subscribe(listener);
}

const AccentOverride = createContext<AccentPreference | null>(null);

/**
 * The screens before sign-in (landing, sign-in, consent) wear Recall's indigo whatever
 * accent the phone has picked: a Berry pick turned the landing pink (2026-11-07). Every
 * `useTheme()` inside reads the brand accent, so the showcase card and page dots follow.
 */
export function BrandAccent({ children }: { children: ReactNode }) {
  return createElement(AccentOverride.Provider, { value: DEFAULT_ACCENT }, children);
}

/** The accent color the user picked (Settings → Accent color), or the brand's inside `BrandAccent`. */
export function useAccentPreference(): AccentPreference {
  const override = useContext(AccentOverride);
  const picked = useSyncExternalStore(subscribeAccent, getAccentSnapshot, getAccentSnapshot);
  return override ?? picked;
}
