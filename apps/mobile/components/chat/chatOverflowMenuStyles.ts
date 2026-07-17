import { StyleSheet } from "react-native";

import type { Theme } from "@/lib/theme";

/** Shared ChatGPT-style overflow card styles (chat ⋮ + drawer long-press). */
export function makeChatOverflowMenuStyles(C: Theme) {
  return StyleSheet.create({
    root: {
      ...StyleSheet.absoluteFill,
      zIndex: 400,
      elevation: 24,
    },
    backdrop: {
      ...StyleSheet.absoluteFill,
      backgroundColor: C.isDark ? "rgba(0,0,0,0.45)" : "rgba(0,0,0,0.18)",
    },
    panelShadow: {
      position: "absolute",
      borderRadius: 24,
      backgroundColor: C.bg,
      shadowColor: "#000",
      shadowOpacity: C.isDark ? 0.5 : 0.22,
      shadowRadius: 28,
      shadowOffset: { width: 0, height: 12 },
      elevation: 22,
    },
    panel: {
      borderRadius: 24,
      backgroundColor: C.bg,
      overflow: "hidden",
      paddingBottom: 8,
    },
    title: {
      fontSize: 15,
      fontWeight: "500",
      color: C.textTertiary,
      paddingHorizontal: 20,
      paddingTop: 18,
      paddingBottom: 10,
    },
    rows: {
      paddingBottom: 6,
    },
    item: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 20,
      paddingVertical: 14,
      gap: 16,
    },
    itemPressed: {
      backgroundColor: C.surfaceAlt,
    },
    label: {
      fontSize: 17,
      color: C.text,
      fontWeight: "500",
      flex: 1,
    },
    labelDanger: { color: C.danger },
  });
}

export type ChatOverflowMenuStyles = ReturnType<typeof makeChatOverflowMenuStyles>;

/** Default insets for the floating card under the top chrome. */
export const CHAT_OVERFLOW_MENU_INSET = {
  right: 12,
  left: 44,
  belowHeader: 6,
} as const;
