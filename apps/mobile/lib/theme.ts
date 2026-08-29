/**
 * App theme — one palette via `useTheme()`. Neutral surfaces + one indigo
 * accent for primary actions, selection, progress, links, and focus.
 * Success / goal-met stays green so “done” is not the same hue as brand.
 * Do not hardcode hex in components — add a token here instead.
 *
 * Canonical names used across the app:
 *  `bg` (background), `surface`, `text` (textPrimary), `textSecondary`,
 *  `border`, `primary` / `accent` (same indigo).
 */
import { useResolvedColorScheme } from "@/hooks/useResolvedColorScheme";

export type Theme = {
  scheme: "light" | "dark";
  isDark: boolean;

  // Brand — actions, links, selection, progress, focus
  primary: string;
  primaryLight: string;
  primaryDark: string;

  // Same indigo as primary — reserved name for AI-in-progress moments
  accent: string;
  accentLight: string;
  accentDark: string;

  // Surfaces — `bg` is the page; `surface` / `inputBg` are raised planes
  bg: string;
  surface: string;
  surfaceAlt: string;
  border: string;

  // Text
  text: string;
  textSecondary: string;
  /** Readable meta/captions — must pass WCAG AA (4.5:1) on `bg` and `surfaceAlt`. */
  textTertiary: string;
  /** Placeholders and non-readable decoration only — not helper or metadata copy. */
  textDisabled: string;

  // Bubbles
  userBubble: string;
  userText: string;
  assistantBubble: string;
  assistantText: string;

  // Composer
  composerBg: string;
  composerBorder: string;
  inputBg: string;

  // Copyable / content panels
  contentSurface: string;

  // Status
  danger: string;
  dangerLight: string;
  warning: string;
  /** Ink on `warning` — banner labels must pass WCAG AA. */
  onWarning: string;
  /** Goal met / daily complete — one green for bars, labels, and dots. */
  success: string;
  successLight: string;
  onPrimary: string;

  // Code blocks
  codeBg: string;
  codeText: string;
  codeLang: string;

  // Overlays
  scrim: string;

  // Media surfaces (camera scanner, attachment viewer) — scheme-invariant.
  // Camera chrome must not invert: white ink reads on a live camera feed in
  // both light and dark, and the crop mask is always a dark overlay.
  onMedia: string;
  mediaScrim: string;

  // Brand identity colors (constant across schemes — logos never invert)
  brand: {
    twitter: string;
    linkedin: string;
    gmail: string;
    /** Google "G" blue — vendor-mandated, same in light & dark. */
    google: string;
    /** Apple Sign-In button fill (black) and its ink (white) — vendor-mandated. */
    apple: string;
    appleInk: string;
  };
};

export const lightTheme: Theme = {
  scheme: "light",
  isDark: false,

  primary: "#4F56E5",
  primaryLight: "#E4E6FF",
  primaryDark: "#3E45C9",

  accent: "#4F56E5",
  accentLight: "#E4E6FF",
  accentDark: "#3E45C9",

  bg: "#FFFFFF",
  surface: "#F7F7F8",
  surfaceAlt: "#EBEBED",
  border: "#D9D9DE",

  text: "#111113",
  textSecondary: "#5C5C64",
  textTertiary: "#67676F",
  textDisabled: "#8E8E96",

  userBubble: "#EAF7F3",
  userText: "#111113",
  assistantBubble: "#FFFFFF",
  assistantText: "#111113",

  composerBg: "#FFFFFF",
  composerBorder: "#D9D9DE",
  inputBg: "#F7F7F8",

  contentSurface: "#F7F7F8",

  danger: "#D92D20",
  dangerLight: "#FDECEC",
  warning: "#B54708",
  onWarning: "#FFFFFF",
  success: "#16845B",
  successLight: "#EAF7F3",
  onPrimary: "#FFFFFF",

  codeBg: "#F7F7F8",
  codeText: "#111113",
  codeLang: "#5C5C64",

  scrim: "rgba(0,0,0,0.40)",

  onMedia: "#FFFFFF",
  mediaScrim: "#000000",

  brand: { twitter: "#1DA1F2", linkedin: "#0A66C2", gmail: "#EA4335", google: "#4285F4", apple: "#000000", appleInk: "#FFFFFF" },
};

export const darkTheme: Theme = {
  scheme: "dark",
  isDark: true,

  primary: "#B4B8FF",
  primaryLight: "#2A2D6A",
  primaryDark: "#9AA0F5",

  accent: "#B4B8FF",
  accentLight: "#2A2D6A",
  accentDark: "#9AA0F5",

  bg: "#0F0F10",
  surface: "#202023",
  surfaceAlt: "#171719",
  border: "#3A3A42",

  text: "#F5F5F6",
  textSecondary: "#A5A5AC",
  textTertiary: "#8A8A92",
  textDisabled: "#7B7B83",

  userBubble: "#12372E",
  userText: "#F5F5F6",
  assistantBubble: "#0F0F10",
  assistantText: "#F5F5F6",

  composerBg: "#0F0F10",
  composerBorder: "#3A3A42",
  inputBg: "#171719",

  contentSurface: "#202023",

  danger: "#FF6B6B",
  dangerLight: "#3B1513",
  warning: "#F5A524",
  onWarning: "#111113",
  success: "#32C48D",
  successLight: "rgba(50, 196, 141, 0.18)",
  onPrimary: "#0F0F10",

  codeBg: "#171719",
  codeText: "#F5F5F6",
  codeLang: "#7B7B83",

  scrim: "rgba(0,0,0,0.60)",

  onMedia: "#FFFFFF",
  mediaScrim: "#000000",

  brand: { twitter: "#1DA1F2", linkedin: "#0A66C2", gmail: "#EA4335", google: "#4285F4", apple: "#000000", appleInk: "#FFFFFF" },
};

/** Active palette for the current color scheme (system or user override). */
export function useTheme(): Theme {
  return useResolvedColorScheme() === "dark" ? darkTheme : lightTheme;
}

const HEX_COLOR_RE = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const RGB_COLOR_RE = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*[\d.]+\s*)?\)$/;

/**
 * Apply an alpha channel to any theme color — hex or already-rgba(...) alike
 * — so fades/scrims/tints don't need format-specific handling. Components
 * used to do this by string-concatenating a hex alpha suffix directly onto a
 * token (e.g. `` `${theme.bg}FA` ``), which only works when that token
 * happens to be a 6-digit hex string. It silently produces an invalid color
 * (and a blank/opaque render) the moment it's applied to a token that is
 * already `rgba(...)` — which `theme.scrim` and dark mode's `successLight`
 * already are. `alpha` is 0-1; unrecognized formats are returned unchanged
 * rather than mangled.
 */
export function withAlpha(color: string, alpha: number): string {
  const clamped = Math.max(0, Math.min(1, alpha));
  const hex = color.match(HEX_COLOR_RE)?.[1];
  if (hex) {
    const full = hex.length === 3 ? hex.split("").map((c) => c + c).join("") : hex;
    const r = parseInt(full.slice(0, 2), 16);
    const g = parseInt(full.slice(2, 4), 16);
    const b = parseInt(full.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${clamped})`;
  }
  const rgb = color.match(RGB_COLOR_RE);
  if (rgb) {
    return `rgba(${rgb[1]}, ${rgb[2]}, ${rgb[3]}, ${clamped})`;
  }
  return color;
}
