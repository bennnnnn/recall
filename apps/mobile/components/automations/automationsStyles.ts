import { StyleSheet } from "react-native";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import type { Theme } from "@/lib/theme";
import { Type } from "@/lib/type";

const TASK_RADIUS = 28;

export function makeAutomationsStyles(C: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: C.bg },
    content: { paddingHorizontal: Space.md, paddingTop: Space.lg, paddingBottom: 116 },
    listGap: { height: Space.md },

    card: {
      backgroundColor: C.surface,
      borderRadius: TASK_RADIUS,
      paddingHorizontal: Space.lg,
      paddingTop: Space.lg,
      paddingBottom: Space.lg,
      gap: Space.xs,
    },
    cardPressed: { opacity: 0.76 },
    cardPaused: {},
    cardEyebrow: {
      ...Type.overline,
      color: C.primary,
      marginBottom: Space.xs,
    },
    cardEyebrowMuted: { color: C.textTertiary },
    cardTitle: {
      ...Type.title,
      fontWeight: "700",
      color: C.text,
    },
    cardDescription: {
      ...Type.body,
      fontSize: 18,
      lineHeight: 27,
      color: C.textSecondary,
      marginTop: Space.xxs,
    },
    cardDivider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: C.border,
      marginTop: Space.md,
    },
    cardFooter: {
      ...Type.body,
      fontSize: 16,
      lineHeight: 22,
      color: C.textTertiary,
      marginTop: Space.sm,
    },

    // Retained for the edit sheet and older component tests.
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

    detailScroll: { flex: 1 },
    detailContent: {
      paddingHorizontal: Space.md,
      paddingTop: Space.lg,
      paddingBottom: Space.xl,
      gap: Space.md,
    },
    detailTaskCard: {
      backgroundColor: C.surface,
      borderRadius: TASK_RADIUS,
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
      fontSize: 18,
      lineHeight: 27,
      color: C.text,
    },
    detailDivider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: C.border,
    },
    detailSettingsGroup: {
      backgroundColor: C.surface,
      borderRadius: TASK_RADIUS,
      overflow: "hidden",
    },
    detailSettingRow: {
      minHeight: 82,
      paddingHorizontal: Space.lg,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.md,
    },
    detailSettingPressed: { opacity: 0.68 },
    detailSettingLabel: {
      ...Type.body,
      fontSize: 18,
      lineHeight: 24,
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
      ...Type.body,
      fontSize: 18,
      lineHeight: 24,
      color: C.textSecondary,
      textAlign: "right",
      flexShrink: 1,
    },
    detailHeaderActions: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: Space.xxs,
      borderRadius: Radius.full,
      backgroundColor: C.surface,
    },
    detailHeaderSeparator: {
      width: StyleSheet.hairlineWidth,
      height: 24,
      backgroundColor: C.border,
    },

    // Kept for the internal history component, though task detail no longer
    // renders a transcript or a large "Not run yet" empty state.
    transcriptList: { flex: 1, marginTop: Space.sm },
    transcriptContent: {
      paddingHorizontal: Space.md,
      paddingTop: 0,
      paddingBottom: Space.xl,
      flexGrow: 1,
    },
  });
}
