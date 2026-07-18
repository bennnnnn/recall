/**
 * App theme — a single standardized palette (Tailwind-derived) shared by
 * every screen via `useTheme()`. Two brand hues: `primary` (blue) drives
 * ordinary buttons/links/selection state; `accent` (indigo/purple) is
 * reserved for AI-in-progress moments (typing/streaming/reasoning
 * indicators) so those reads as distinctly "the model is working" rather
 * than a generic interactive color. Do not hardcode hex colors in
 * components — add a token here instead so every screen stays in sync.
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

  primary: "#2563EB",
  primaryLight: "#DBEAFE",
  primaryDark: "#1D4ED8",

  accent: "#4F46E5",
  accentLight: "#E0E7FF",
  accentDark: "#4338CA",

  // From chat screenshot: off-white page, pure-white chrome, cool-gray bubbles.
  bg: "#FAFAFA",
  surface: "#FFFFFF",
  surfaceAlt: "#F1F4F9",
  border: "#E8E8ED",

  text: "#111827",
  textSecondary: "#6B7280",
  textTertiary: "#9CA3AF",

  userBubble: "#F1F4F9",
  userText: "#111827",
  assistantBubble: "#FFFFFF",
  assistantText: "#111827",

  composerBg: "#FAFAFA",
  composerBorder: "#E8E8ED",
  inputBg: "#FFFFFF",

  contentSurface: "#F1F4F9",

  danger: "#EF4444",
  dangerLight: "#FEE2E2",
  warning: "#F59E0B",
  success: "#22C55E",
  successLight: "#DCFCE7",
  onPrimary: "#FFFFFF",

  codeBg: "#F8FAFC",
  codeText: "#111827",
  codeLang: "#9CA3AF",

  scrim: "rgba(0,0,0,0.40)",

  brand: { twitter: "#1DA1F2", linkedin: "#0A66C2", gmail: "#EA4335" },
};

export const darkTheme: Theme = {
  scheme: "dark",
  isDark: true,

  primary: "#3B82F6",
  primaryLight: "#1E2A47",
  primaryDark: "#60A5FA",

  accent: "#818CF8",
  accentLight: "#21203D",
  accentDark: "#A5B4FC",

  // Deeper canvas, raised surface — same hierarchy as light, inverted.
  bg: "#1C1C1E",
  surface: "#2C2C2E",
  surfaceAlt: "#3A3A3C",
  border: "#3A3A3C",

  text: "#ECECEC",
  textSecondary: "#B4B4B4",
  textTertiary: "#8E8E8E",

  userBubble: "#2C2C2E",
  userText: "#ECECEC",
  assistantBubble: "#1C1C1E",
  assistantText: "#ECECEC",

  composerBg: "#1C1C1E",
  composerBorder: "#3A3A3C",
  inputBg: "#2C2C2E",

  contentSurface: "#2C2C2E",

  danger: "#F87171",
  dangerLight: "#3A1F1E",
  warning: "#FBBF24",
  success: "#4ADE80",
  successLight: "rgba(74, 222, 128, 0.16)",
  onPrimary: "#FFFFFF",

  codeBg: "#0D0D0D",
  codeText: "#E6E6E6",
  codeLang: "#8E8E8E",

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
