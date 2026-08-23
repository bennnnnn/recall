/**
 * App theme — one palette via `useTheme()`. Chat canvas follows ChatGPT
 * mobile: light gray page, white cards, mint user chip.
 *  - `primary` — Recall action blue for buttons, links, send, selection
 *  - `accent` — teal reserved for AI-in-progress (typing/streaming/reasoning)
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

  // Surfaces — `bg` is the chat page; `surface` / `inputBg` are raised planes
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

  // iOS system blue family — unmistakable interactive color
  primary: "#007AFF",
  primaryLight: "#E5F2FF",
  primaryDark: "#0056CC",

  // Teal — clearly not blue; reserved for "model is working"
  accent: "#0D9488",
  accentLight: "#CCFBF1",
  accentDark: "#0F766E",

  // ChatGPT mobile: gray page, white raised cards
  bg: "#F7F7F7",
  surface: "#FFFFFF",
  surfaceAlt: "#F0F0F0",
  border: "#E5E5E5",

  text: "#0D0D0D",
  textSecondary: "#5D5D5D",
  textTertiary: "#8F8F8F",

  // ChatGPT mobile user chip — mint on gray; assistant prose sits on the page
  userBubble: "#E8F5E9",
  userText: "#0D0D0D",
  assistantBubble: "#F7F7F7",
  assistantText: "#0D0D0D",

  composerBg: "#F7F7F7",
  composerBorder: "#E5E5E5",
  inputBg: "#FFFFFF",

  contentSurface: "#FFFFFF",

  danger: "#FF3B30",
  dangerLight: "#FFE5E3",
  warning: "#FF9F0A",
  success: "#34C759",
  successLight: "#D8F5E1",
  onPrimary: "#FFFFFF",

  codeBg: "#F0F0F0",
  codeText: "#0D0D0D",
  codeLang: "#8F8F8F",

  scrim: "rgba(0,0,0,0.40)",

  onMedia: "#FFFFFF",
  mediaScrim: "#000000",

  brand: { twitter: "#1DA1F2", linkedin: "#0A66C2", gmail: "#EA4335", google: "#4285F4", apple: "#000000", appleInk: "#FFFFFF" },
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

  bg: "#212121",
  surface: "#2F2F2F",
  surfaceAlt: "#2F2F2F",
  border: "#3E3E3E",

  text: "#ECECEC",
  textSecondary: "#B4B4B4",
  textTertiary: "#8F8F8F",

  userBubble: "#2F2F2F",
  userText: "#ECECEC",
  assistantBubble: "#212121",
  assistantText: "#ECECEC",

  composerBg: "#212121",
  composerBorder: "#3E3E3E",
  inputBg: "#2F2F2F",

  contentSurface: "#2F2F2F",

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
