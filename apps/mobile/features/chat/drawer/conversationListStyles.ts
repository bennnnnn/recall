import { StyleSheet } from "react-native";

import { Radius } from "@/lib/radius";
import { shadowRaised } from "@/lib/shadow";
import { Space } from "@/lib/space";
import type { Theme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

export const TOP_CHROME = 58;
// The bottom bar over its safe area: 12 above a 44-pt row, and the hairline on top.
export const FOOTER_CHROME = 57;
export const FADE_EXTRA = 40;

export function makeConversationListStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg, overflow: "visible" },
    topFade: { position: "absolute", top: 0, left: 0, right: 0, zIndex: 50 },
    bottomFade: {
      position: "absolute",
      bottom: 0,
      left: 0,
      right: 0,
      zIndex: 50,
    },
    topOverlay: {
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      zIndex: 100,
      // Transparent so the header fade dims titles sliding under Recall's mark and
      // search, which paint above that veil (the owner, 2026-11-11).
      backgroundColor: "transparent",
    },
    header: { paddingHorizontal: Space.md, paddingBottom: Space.sm },
    drawerNav: {
      paddingBottom: Space.md,
      marginBottom: Space.xxs,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    logo: { flexDirection: "row", alignItems: "center", gap: Space.xs },
    selectionHeader: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
    },
    selectionHeaderTitle: {
      flex: 1,
      textAlign: "center",
      ...Type.body,
      ...Weight.bold,
      color: theme.text,
    },
    selectionHeaderAction: {
      paddingHorizontal: Space.xxs,
      paddingVertical: 2,
    },
    selectionHeaderActionText: {
      ...Type.secondary,
      ...Weight.semibold,
      color: theme.primary,
    },
    searchCancel: { paddingLeft: Space.xxs },
    searchCancelText: {
      ...Type.secondary,
      ...Weight.semibold,
      color: theme.primary,
    },
    navRow: {
      marginHorizontal: Space.md,
      marginBottom: Space.xxs,
      paddingHorizontal: Space.md,
    },
    // One icon box for each nav row (To-do, Library), lined up with the chat rows below.
    navIconWrap: {
      width: 22,
      height: 22,
      alignItems: "center",
      justifyContent: "center",
    },
    navBadge: { position: "absolute", top: -6, right: -10 },
    list: { flex: 1 },
    section: { marginTop: Space.md },
    sectionTitle: {
      ...Type.overline,
      color: theme.textTertiary,
      paddingHorizontal: Space.md,
      marginBottom: 2,
    },
    sectionHeader: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      marginTop: Space.md,
      paddingHorizontal: Space.md,
      paddingVertical: Space.xxs,
    },
    sectionCount: {
      ...Type.meta,
      color: theme.textTertiary,
      marginLeft: "auto",
    },
    footer: {
      position: "absolute",
      bottom: 0,
      left: 0,
      right: 0,
      zIndex: 100,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      paddingHorizontal: Space.md,
      paddingTop: Space.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
    },
    // The bottom bar is solid: titles scroll under it, never show through.
    chromeBar: { backgroundColor: theme.bg },
    headerSearch: { flex: 1 },
    appMark: { width: 32, height: 32, borderRadius: Radius.sm },
    headerIconBtn: {
      marginLeft: "auto",
      width: Space.minTouch,
      height: Space.minTouch,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: Radius.full,
    },
    accountRow: {
      flex: 1,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
      minHeight: Space.minTouch,
    },
    accountName: { ...Type.body, ...Weight.semibold, color: theme.text, flexShrink: 1 },
    newChatBtn: {
      width: Space.minTouch,
      height: Space.minTouch,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: Radius.full,
      backgroundColor: theme.primary,
      ...shadowRaised(theme),
    },
    selectionBar: {
      position: "absolute",
      bottom: 0,
      left: 0,
      right: 0,
      zIndex: 100,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-evenly",
      paddingHorizontal: Space.md,
      paddingTop: Space.sm,
      backgroundColor: theme.bg,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
    },
    selectionAction: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xxs,
      paddingVertical: Space.xs,
      paddingHorizontal: Space.sm,
    },
    selectionActionDisabled: {
      opacity: 0.45,
    },
    selectionActionText: {
      ...Type.secondary,
      ...Weight.semibold,
      color: theme.primary,
    },
    selectionActionTextDanger: {
      color: theme.danger,
    },
    selectionActionTextDisabled: {
      color: theme.textTertiary,
    },
  });
}

export type ConversationListStyles = ReturnType<typeof makeConversationListStyles>;
