import { StyleSheet } from "react-native";

import type { Theme } from "@/lib/theme";

export function makeChatScreenStyles(C: Theme) {
  return StyleSheet.create({
    center: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: C.bg,
    },
    loadingDot: { fontSize: 48, color: C.primary, opacity: 0.4 },
    container: { flex: 1, backgroundColor: C.bg },
    quotaNudge: {
      position: "absolute",
      left: 8,
      right: 8,
      flexDirection: "row",
      alignItems: "center",
      backgroundColor: C.surface,
      borderRadius: 12,
      paddingHorizontal: 10,
      paddingVertical: 8,
      gap: 8,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      shadowColor: "#000",
      shadowOpacity: 0.08,
      shadowRadius: 6,
      shadowOffset: { width: 0, height: 2 },
      elevation: 2,
    },
    quotaNudgeBody: { flex: 1, flexDirection: "row", alignItems: "center", gap: 8 },
    quotaNudgeIcon: { flexShrink: 0 },
    quotaNudgeText: { flex: 1, fontSize: 13, color: C.text, lineHeight: 18 },
    quotaNudgeCta: {
      backgroundColor: C.primary,
      borderRadius: 8,
      paddingHorizontal: 10,
      paddingVertical: 6,
      flexShrink: 0,
    },
    quotaNudgeCtaText: { color: C.onPrimary, fontSize: 13, fontWeight: "700" },
    quotaNudgeClose: { padding: 4, flexShrink: 0 },
  });
}

export type ChatScreenStyles = ReturnType<typeof makeChatScreenStyles>;
