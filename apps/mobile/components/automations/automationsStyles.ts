import { StyleSheet } from "react-native";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import type { Theme } from "@/lib/theme";
import { Type } from "@/lib/type";

export function makeAutomationsStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    content: { padding: Space.md, paddingBottom: 96 },
    listGap: { height: Space.md },

    card: {
      backgroundColor: C.surfaceAlt,
      borderRadius: Radius.sheet,
      paddingHorizontal: Space.lg,
      paddingTop: Space.lg,
      paddingBottom: Space.md,
      gap: Space.xs,
    },
    cardPressed: { opacity: 0.82 },
    cardPaused: { opacity: 0.62 },
    cardEyebrow: {
      ...Type.overline,
      color: C.primary,
      marginBottom: Space.xs,
    },
    cardTitle: {
      ...Type.title,
      fontWeight: "700",
      color: C.text,
    },
    cardDescription: {
      ...Type.body,
      color: C.textSecondary,
      marginTop: Space.xxs,
    },
    cardDivider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: C.border,
      marginTop: Space.md,
    },
    cardFooter: {
      ...Type.secondary,
      color: C.textTertiary,
      marginTop: Space.sm,
    },

    // Legacy status/meta roles are still used by older snapshots/tests and by
    // the paused detail treatment. Keep them neutral while the card itself
    // uses the simpler Tasks-style hierarchy above.
    cardMetaRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      flexWrap: "wrap",
    },
    cardMetaText: { ...Type.caption, color: C.textSecondary },
    cardPrompt: { ...Type.body, color: C.text },
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

    detailContent: {
      paddingHorizontal: Space.md,
      paddingTop: Space.md,
      gap: Space.md,
    },
    detailTaskCard: {
      backgroundColor: C.surfaceAlt,
      borderRadius: Radius.sheet,
      overflow: "hidden",
    },
    detailTaskSection: {
      paddingHorizontal: Space.lg,
      paddingVertical: Space.lg,
    },
    detailTaskTitle: {
      ...Type.title,
      fontWeight: "500",
      color: C.text,
    },
    detailPrompt: {
      ...Type.body,
      color: C.text,
    },
    detailDivider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: C.border,
      marginLeft: Space.lg,
    },
    detailSettingsGroup: {
      backgroundColor: C.surfaceAlt,
      borderRadius: Radius.sheet,
      overflow: "hidden",
    },
    detailSettingRow: {
      minHeight: 70,
      paddingHorizontal: Space.lg,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.md,
    },
    detailSettingLabel: {
      ...Type.body,
      color: C.text,
      flexShrink: 0,
    },
    detailSettingRight: {
      flex: 1,
      flexDirection: "row",
      justifyContent: "flex-end",
      alignItems: "center",
      gap: Space.xs,
    },
    detailSettingValue: {
      ...Type.navTitle,
      fontWeight: "400",
      color: C.textSecondary,
      textAlign: "right",
      flexShrink: 1,
    },
    detailHeaderActions: {
      flexDirection: "row",
      alignItems: "center",
      gap: 2,
      paddingHorizontal: Space.xxs,
      borderRadius: Radius.full,
      backgroundColor: C.surfaceAlt,
    },

    // Kept for the latest run history below the task controls. The task editor
    // is the primary surface; history only appears once the automation has run.
    transcriptList: { flex: 1, marginTop: Space.sm },
    transcriptContent: {
      paddingHorizontal: Space.md,
      paddingTop: 0,
      paddingBottom: Space.xl,
      flexGrow: 1,
    },
  });
}
