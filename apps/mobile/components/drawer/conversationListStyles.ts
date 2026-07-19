import { StyleSheet } from "react-native";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import type { Theme } from "@/lib/theme";
import { Type } from "@/lib/type";

export const TOP_CHROME = 58;
/** Fixed Learning / Lists / Reminders block under the logo row. */
export const DRAWER_NAV_CHROME = 160;
export const FOOTER_CHROME = 54;
export const FADE_EXTRA = 40;

export function makeConversationListStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg, overflow: "visible" },
    center: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xs,
    },
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
      // Solid so Learning/Lists/Reminders sit above the scroll fade (not washed out).
      backgroundColor: theme.bg,
    },
    header: { paddingHorizontal: Space.md, paddingBottom: Space.sm },
    drawerNav: {
      paddingBottom: Space.md,
      marginBottom: Space.xxs,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    logo: { flexDirection: "row", alignItems: "center", gap: Space.xs },
    logoText: {
      fontSize: 20,
      fontWeight: "800",
      color: theme.text,
      letterSpacing: -0.5,
    },
    headerActions: {
      marginLeft: "auto",
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xxs,
    },
    searchBtn: { padding: Space.xxs },
    selectionHeader: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
    },
    selectionHeaderTitle: {
      flex: 1,
      textAlign: "center",
      ...Type.body,
      fontWeight: "700",
      color: theme.text,
    },
    selectionHeaderAction: {
      paddingHorizontal: Space.xxs,
      paddingVertical: 2,
    },
    selectionHeaderActionText: {
      ...Type.secondary,
      fontWeight: "600",
      color: theme.primary,
    },
    searchBar: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      backgroundColor: theme.surface,
      borderRadius: Radius.md,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
    },
    searchInput: {
      flex: 1,
      ...Type.body,
      color: theme.text,
      paddingVertical: 0,
      minHeight: 22,
    },
    searchCancel: { paddingLeft: Space.xxs },
    searchCancelText: {
      ...Type.secondary,
      fontWeight: "600",
      color: theme.primary,
    },
    todosLink: {
      flexDirection: "row",
      alignItems: "center",
      marginHorizontal: Space.md,
      marginBottom: Space.xxs,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      gap: Space.sm,
    },
    // Same primary ink for Learning / Lists / Reminders (and chat rows below).
    todosLinkText: {
      flex: 1,
      ...Type.secondary,
      fontWeight: "600",
      color: theme.text,
    },
    todosChevron: { marginLeft: "auto" },
    navIconWrap: {
      width: 22,
      height: 22,
      alignItems: "center",
      justifyContent: "center",
    },
    navBadge: { position: "absolute", top: -6, right: -10 },
    list: { flex: 1 },
    section: { marginTop: 18 },
    sectionTitle: {
      ...Type.caption,
      fontSize: 11,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.8,
      paddingHorizontal: Space.md,
      marginBottom: 2,
    },
    sectionHeader: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      marginTop: 18,
      paddingHorizontal: Space.md,
      paddingVertical: Space.xxs,
    },
    sectionCount: {
      fontSize: 12,
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
      paddingHorizontal: Space.md,
      paddingTop: Space.sm,
      backgroundColor: "transparent",
    },
    footerNewChat: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      paddingVertical: Space.xs,
      paddingHorizontal: Space.sm,
      borderRadius: Radius.sm,
      backgroundColor: theme.primary,
    },
    footerNewChatText: { ...Type.label, color: theme.onPrimary },
    settingsBtn: {
      marginLeft: "auto",
      padding: Space.xs,
      borderRadius: Radius.sm,
      backgroundColor: theme.primary,
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
      fontWeight: "600",
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
