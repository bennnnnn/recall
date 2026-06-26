// Legacy default export for scaffold components
const Colors = {
  light: {
    text: "#0F0F0F",
    background: "#fff",
    tint: "#6C47FF",
    tabIconDefault: "#ccc",
    tabIconSelected: "#6C47FF",
  },
  dark: {
    text: "#fff",
    background: "#000",
    tint: "#6C47FF",
    tabIconDefault: "#ccc",
    tabIconSelected: "#6C47FF",
  },
};
export default Colors;

export const C = {
  // Brand
  primary: "#6C47FF",
  primaryLight: "#EDE9FF",
  primaryDark: "#4B2FD4",

  // Surfaces
  bg: "#FFFFFF",
  surface: "#F5F5F7",
  surfaceAlt: "#EFEFEF",
  border: "#E5E5EA",

  // Text
  text: "#0F0F0F",
  textSecondary: "#6B6B6B",
  textTertiary: "#AEAEB2",

  // Bubbles
  userBubble: "#F4F4F4",
  userText: "#0F0F0F",
  assistantBubble: "#FFFFFF",
  assistantText: "#0F0F0F",

  // Copyable / code panels (slightly off app white)
  contentSurface: "#F7F7F8",

  // Status
  danger: "#FF3B30",
  dangerLight: "#FFF0EF",

  // Code blocks — soft light panel (matches copy cards)
  codeBg: "#F7F7F8",
  codeText: "#1F2328",
  codeLang: "#6B6B6B",
} as const;
