import { StyleSheet } from "react-native";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import type { Theme } from "@/lib/theme";
import { Type } from "@/lib/type";

export function makeAutomationsStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    content: { padding: Space.md, paddingBottom: 96 },
    listGap: { height: Space.sm },

    card: {
      backgroundColor: C.surface,
      borderRadius: Radius.md,
      borderWidth: 1,
      borderColor: C.border,
      padding: Space.md,
      gap: Space.xs,
    },
    cardPaused: { opacity: 0.6 },
    cardPrompt: { ...Type.body, color: C.text },
    cardMetaRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      flexWrap: "wrap",
    },
    cardMetaText: { ...Type.caption, color: C.textSecondary },
    cardStatusPill: {
      paddingHorizontal: Space.xs,
      paddingVertical: 2,
      borderRadius: Radius.full,
      backgroundColor: C.primaryLight,
    },
    cardStatusPillPaused: { backgroundColor: C.surfaceAlt },
    cardStatusPillText: {
      ...Type.caption,
      fontSize: 11,
      fontWeight: "700",
      color: C.primary,
    },
    cardStatusPillTextPaused: { color: C.textTertiary },
    cardLastRunOk: { color: C.textTertiary },
    cardLastRunError: { color: C.danger },

    formLabel: { ...Type.label, color: C.textSecondary },
    fieldGap: { marginTop: Space.md },
    promptInput: {
      ...Type.navTitle,
      color: C.text,
      backgroundColor: C.surface,
      borderRadius: Radius.md,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      borderWidth: 1,
      borderColor: C.border,
      minHeight: 88,
      textAlignVertical: "top",
    },
    dateChip: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      backgroundColor: C.primaryLight,
      borderRadius: Radius.sm,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.sm,
      alignSelf: "flex-start",
    },
    dateChipText: { ...Type.secondary, fontWeight: "600", color: C.text },
    frequencyField: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.xs,
      minHeight: Space.minTouch,
      backgroundColor: C.surface,
      borderRadius: Radius.md,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      borderWidth: 1,
      borderColor: C.border,
    },
    frequencyFieldOpen: {
      borderBottomLeftRadius: 0,
      borderBottomRightRadius: 0,
    },
    frequencyFieldText: {
      flex: 1,
      ...Type.navTitle,
      color: C.text,
    },
    sheet: {
      backgroundColor: C.surface,
      borderTopLeftRadius: Radius.sheet,
      borderTopRightRadius: Radius.sheet,
    },
    sheetBody: { padding: Space.md, paddingBottom: Space.xl, gap: Space.xs },

    detailHeader: {
      padding: Space.md,
      gap: Space.xs,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: C.border,
    },
    detailPrompt: { ...Type.navTitle, fontWeight: "700", color: C.text },
    detailMetaRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      flexWrap: "wrap",
    },
    detailMetaText: { ...Type.secondary, color: C.textSecondary },
    detailStatusPill: { alignSelf: "flex-start" },
    detailHeaderActions: { flexDirection: "row", alignItems: "center", gap: 2 },

    // ChatGPT Task-detail-style "Repeat / Time / Last run" card — Repeat and
    // Time are directly editable in place (tap → inline picker, same
    // components AddAutomationSheet uses), auto-saving on select/close. Last
    // run is read-only. Editing the prompt text itself still goes through
    // the kebab → Edit sheet.
    detailInfoCard: {
      margin: Space.md,
      backgroundColor: C.surface,
      borderRadius: Radius.md,
      borderWidth: 1,
      borderColor: C.border,
      overflow: "hidden",
    },
    detailInfoRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      minHeight: Space.minTouch,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      gap: Space.sm,
    },
    detailInfoRowBorder: {
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: C.border,
    },
    detailInfoRowOpen: { backgroundColor: C.surfaceAlt },
    detailInfoLabel: { ...Type.body, color: C.text },
    detailInfoValue: { ...Type.secondary, color: C.textSecondary, flexShrink: 1, textAlign: "right" },
    detailInfoValueGroup: { flexDirection: "row", alignItems: "center", gap: Space.xxs },
    detailPickerWrap: {
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: C.border,
      paddingVertical: Space.xs,
      backgroundColor: C.surfaceAlt,
    },
  });
}
