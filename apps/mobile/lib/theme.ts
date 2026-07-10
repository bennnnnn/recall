/**
 * App theme — ChatGPT-style light & dark palettes that follow the system
 * color scheme. All live screens consume the palette via `useTheme()`; the
 * legacy static `C` object and its scaffold consumers (Themed/StyledText/
 * EditScreenInfo) have been removed.
 */
import { useResolvedColorScheme } from "@/hooks/useResolvedColorScheme";

export type Theme = {
  scheme: "light" | "dark";
  isDark: boolean;

  // Brand
  primary: string;
  primaryLight: string;
  primaryDark: string;

  // Surfaces
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
};

export const lightTheme: Theme = {
  scheme: "light",
  isDark: false,

  primary: "#6C47FF",
  primaryLight: "#EDE9FF",
  primaryDark: "#4B2FD4",

  bg: "#FFFFFF",
  surface: "#F4F4F4",
  surfaceAlt: "#ECECEC",
  border: "#E5E5E5",

  text: "#0D0D0D",
  textSecondary: "#5D5D5D",
  textTertiary: "#9B9B9B",

  userBubble: "#F4F4F4",
  userText: "#0D0D0D",
  assistantBubble: "#FFFFFF",
  assistantText: "#0D0D0D",

  composerBg: "#FFFFFF",
  composerBorder: "#E5E5E5",
  inputBg: "#FFFFFF",

  contentSurface: "#F7F7F8",

  danger: "#E5484D",
  dangerLight: "#FFF0EF",
  warning: "#FF9F0A",
  success: "#15803D",
  successLight: "#DCFCE7",
  onPrimary: "#FFFFFF",

  codeBg: "#F7F7F8",
  codeText: "#1F2328",
  codeLang: "#6B6B6B",

  scrim: "rgba(0,0,0,0.40)",
};

export const darkTheme: Theme = {
  scheme: "dark",
  isDark: true,

  primary: "#7C5CFF",
  primaryLight: "#2A2440",
  primaryDark: "#A593FF",

  bg: "#212121",
  surface: "#2F2F2F",
  surfaceAlt: "#3A3A3A",
  border: "#3A3A3A",

  text: "#ECECEC",
  textSecondary: "#B4B4B4",
  textTertiary: "#8E8E8E",

  userBubble: "#2F2F2F",
  userText: "#ECECEC",
  assistantBubble: "#212121",
  assistantText: "#ECECEC",

  composerBg: "#2F2F2F",
  composerBorder: "#3A3A3A",
  inputBg: "#2F2F2F",

  contentSurface: "#2A2A2A",

  danger: "#FF6B60",
  dangerLight: "#3A1F1E",
  warning: "#FF9F0A",
  success: "#4ADE80",
  successLight: "rgba(74, 222, 128, 0.16)",
  onPrimary: "#FFFFFF",

  codeBg: "#0D0D0D",
  codeText: "#E6E6E6",
  codeLang: "#9B9B9B",

  scrim: "rgba(0,0,0,0.60)",
};

/** Active palette for the current color scheme (system or user override). */
export function useTheme(): Theme {
  return useResolvedColorScheme() === "dark" ? darkTheme : lightTheme;
}
