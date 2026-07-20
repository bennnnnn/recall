/**
 * App theme — one palette via `useTheme()`. Strategy mirrors successful chat
 * apps (iMessage / WhatsApp chrome + modern AI products):
 *  - `primary` — one vivid action blue for buttons, links, send, selection
 *  - `accent` — teal reserved for AI-in-progress (typing/streaming/reasoning)
 *    so it never competes with interactive blue
 *  - Soft blue `userBubble` — branded without forcing white-on-blue markdown
 *  - Neutral canvas/surfaces — hierarchy without color noise
 * Do not hardcode hex in components — add a token here instead.
 */
import { useResolvedColorScheme } from "@/hooks/useResolvedColorScheme";

export type Theme = {
  scheme: "light" | "dark";
  isDark: boolean;

  // Brand — ordinary buttons, links, selection/active state
  primary: string;
  primaryLight: string;
  primaryDark: string;

  // Brand — AI-in-progress moments only (typing/streaming/reasoning)
  accent: string;
  accentLight: string;
  accentDark: string;

  // Surfaces — `bg` is the canvas wash; `surface` / `inputBg` are raised planes
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

  // Brand identity colors (constant across schemes — logos never invert)
  brand: {
    twitter: string;
    linkedin: string;
    gmail: string;
  };
};

export const lightTheme: Theme = {
  scheme: "light",
  isDark: false,

  // iOS system blue family — unmistakable interactive color
  primary: "#007AFF",
  primaryLight: "#E5F2FF",
  primaryDark: "#0056CC",

  // Teal — clearly not blue; reserved for "model is working"
  accent: "#0D9488",
  accentLight: "#CCFBF1",
  accentDark: "#0F766E",

  // iOS grouped-background hierarchy
  bg: "#F2F2F7",
  surface: "#FFFFFF",
  surfaceAlt: "#E5E5EA",
  border: "#D1D1D6",

  text: "#1C1C1E",
  textSecondary: "#636366",
  textTertiary: "#8E8E93",

  // Soft brand wash — stands out vs gray assistant without white-on-blue markdown
  userBubble: "#D6EBFF",
  userText: "#1C1C1E",
  assistantBubble: "#FFFFFF",
  assistantText: "#1C1C1E",

  composerBg: "#F2F2F7",
  composerBorder: "#D1D1D6",
  inputBg: "#FFFFFF",

  contentSurface: "#EFEFF4",

  danger: "#FF3B30",
  dangerLight: "#FFE5E3",
  warning: "#FF9F0A",
  success: "#34C759",
  successLight: "#D8F5E1",
  onPrimary: "#FFFFFF",

  codeBg: "#F2F2F7",
  codeText: "#1C1C1E",
  codeLang: "#8E8E93",

  scrim: "rgba(0,0,0,0.40)",

  brand: { twitter: "#1DA1F2", linkedin: "#0A66C2", gmail: "#EA4335" },
};

export const darkTheme: Theme = {
  scheme: "dark",
  isDark: true,

  primary: "#0A84FF",
  primaryLight: "#0A2540",
  primaryDark: "#64B5FF",

  accent: "#2DD4BF",
  accentLight: "#0F2F2C",
  accentDark: "#5EEAD4",

  bg: "#000000",
  surface: "#1C1C1E",
  surfaceAlt: "#2C2C2E",
  border: "#38383A",

  text: "#F5F5F7",
  textSecondary: "#A1A1A6",
  textTertiary: "#8E8E93",

  userBubble: "#0A335C",
  userText: "#F5F5F7",
  assistantBubble: "#1C1C1E",
  assistantText: "#F5F5F7",

  composerBg: "#000000",
  composerBorder: "#38383A",
  inputBg: "#1C1C1E",

  contentSurface: "#1C1C1E",

  danger: "#FF453A",
  dangerLight: "#3B1513",
  warning: "#FFD60A",
  success: "#30D158",
  successLight: "rgba(48, 209, 88, 0.18)",
  onPrimary: "#FFFFFF",

  codeBg: "#0D0D0D",
  codeText: "#E6E6E6",
  codeLang: "#8E8E93",

  scrim: "rgba(0,0,0,0.60)",

  brand: { twitter: "#1DA1F2", linkedin: "#0A66C2", gmail: "#EA4335" },
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
