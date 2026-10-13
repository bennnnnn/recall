/**
 * Accent color — the one brand hue on buttons, links, selection, progress,
 * focus, the user's bubble tint and the first graph series. Indigo is the
 * default and keeps the palette in `lib/theme.ts` exactly as it is.
 *
 * Every preset passes, in both schemes (checked in `__tests__/accent.test.tsx`):
 * primary on the page ≥ 4.5:1 (links and selected text), onPrimary on primary
 * ≥ 4.5:1 (button labels), and the bubble text on userBubble ≥ 7:1.
 * No green (reads as success) and no red (reads as danger).
 */
import type { Theme } from "@/lib/theme";

type AccentTones = {
  primary: string;
  /** Selected wells and soft fills. */
  primaryLight: string;
  /** Pressed state of a primary fill. */
  primaryDark: string;
  /** The user's chat bubble — a quiet tint of the accent. */
  userBubble: string;
  /** Ink on a primary fill. */
  onPrimary: string;
};

type AccentPreset = { light: AccentTones; dark: AccentTones };

export const ACCENTS = {
  indigo: {
    light: {
      primary: "#4F56E5",
      primaryLight: "#E4E6FF",
      primaryDark: "#3E45C9",
      userBubble: "#F0F1FF",
      onPrimary: "#FFFFFF",
    },
    dark: {
      primary: "#B4B8FF",
      primaryLight: "#2A2D6A",
      primaryDark: "#9AA0F5",
      userBubble: "#2A2D6A",
      onPrimary: "#0F0F10",
    },
  },
} as const satisfies Record<string, AccentPreset>;

export type AccentPreference = keyof typeof ACCENTS;

export const DEFAULT_ACCENT: AccentPreference = "indigo";

export const ACCENT_OPTIONS = Object.keys(ACCENTS) as AccentPreference[];

export function normalizeAccentPreference(raw: string | null | undefined): AccentPreference {
  return raw && Object.hasOwn(ACCENTS, raw) ? (raw as AccentPreference) : DEFAULT_ACCENT;
}

/** The swatch a picker shows for a preset in the current scheme. */
export function accentSwatch(accent: AccentPreference, scheme: "light" | "dark"): string {
  return ACCENTS[accent][scheme].primary;
}

/** The theme with one accent's tones in every brand slot. */
export function applyAccent(theme: Theme, accent: AccentPreference): Theme {
  const tones = ACCENTS[accent][theme.scheme];
  return {
    ...theme,
    primary: tones.primary,
    primaryLight: tones.primaryLight,
    primaryDark: tones.primaryDark,
    accent: tones.primary,
    accentLight: tones.primaryLight,
    accentDark: tones.primaryDark,
    userBubble: tones.userBubble,
    onPrimary: tones.onPrimary,
    graphSeries: [tones.primary, theme.graphSeries[1], theme.graphSeries[2], theme.graphSeries[3]],
  };
}
