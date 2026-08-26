/**
 * App theme — one palette via `useTheme()`. Neutral surfaces + one green
 * accent for primary actions, selection, progress, links, and focus.
 * Do not hardcode hex in components — add a token here instead.
 *
 * Canonical names used across the app:
 *  `bg` (background), `surface`, `text` (textPrimary), `textSecondary`,
 *  `border`, `primary` / `accent` (same green).
 */
import { useResolvedColorScheme } from "@/hooks/useResolvedColorScheme";

export type Theme = {
  scheme: "light" | "dark";
  isDark: boolean;

  // Brand — actions, links, selection, progress, focus
  primary: string;
  primaryLight: string;
  primaryDark: string;

  // Same green as primary — reserved name for AI-in-progress moments
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
  textTertiary: string;

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

  primary: "#10A37F",
  primaryLight: "#EAF7F3",
  primaryDark: "#0D8C6D",

  accent: "#10A37F",
  accentLight: "#EAF7F3",
  accentDark: "#0D8C6D",

  bg: "#FFFFFF",
  surface: "#FFFFFF",
  surfaceAlt: "#F7F7F8",
  border: "#E7E7E9",

  text: "#111113",
  textSecondary: "#6B6B73",
  textTertiary: "#8E8E96",

  userBubble: "#EAF7F3",
  userText: "#111113",
  assistantBubble: "#FFFFFF",
  assistantText: "#111113",

  composerBg: "#FFFFFF",
  composerBorder: "#E7E7E9",
  inputBg: "#F7F7F8",

  contentSurface: "#FFFFFF",

  danger: "#D92D20",
  dangerLight: "#FDECEC",
  warning: "#B54708",
  success: "#16845B",
  successLight: "#EAF7F3",
  onPrimary: "#FFFFFF",

  codeBg: "#F7F7F8",
  codeText: "#111113",
  codeLang: "#8E8E96",

  scrim: "rgba(0,0,0,0.40)",

  onMedia: "#FFFFFF",
  mediaScrim: "#000000",

  brand: { twitter: "#1DA1F2", linkedin: "#0A66C2", gmail: "#EA4335", google: "#4285F4", apple: "#000000", appleInk: "#FFFFFF" },
};

export const darkTheme: Theme = {
  scheme: "dark",
  isDark: true,

  primary: "#19C59A",
  primaryLight: "#12372E",
  primaryDark: "#13A982",

  accent: "#19C59A",
  accentLight: "#12372E",
  accentDark: "#13A982",

  bg: "#0F0F10",
  surface: "#202023",
  surfaceAlt: "#171719",
  border: "#2C2C30",

  text: "#F5F5F6",
  textSecondary: "#A5A5AC",
  textTertiary: "#7B7B83",

  userBubble: "#12372E",
  userText: "#F5F5F6",
  assistantBubble: "#0F0F10",
  assistantText: "#F5F5F6",

  composerBg: "#0F0F10",
  composerBorder: "#2C2C30",
  inputBg: "#171719",

  contentSurface: "#202023",

  danger: "#FF6B6B",
  dangerLight: "#3B1513",
  warning: "#F5A524",
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
