import { StyleSheet } from "react-native";

import type { Theme } from "@/lib/theme";

export const TOP_CHROME = 58;
/** Fixed Learning / Lists / Reminders block under the logo row. */
export const DRAWER_NAV_CHROME = 150;
export const FOOTER_CHROME = 54;
export const FADE_EXTRA = 40;
export const CHAT_LIST_STALE_MS = 20_000;

export function makeConversationListStyles(theme: Theme) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: theme.bg, overflow: "visible" },
    center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 8 },
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
    header: { paddingHorizontal: 16, paddingBottom: 10 },
    drawerNav: {
      paddingBottom: 14,
      marginBottom: 4,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: theme.border,
    },
    logo: { flexDirection: "row", alignItems: "center", gap: 8 },
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
      gap: 4,
    },
    searchBtn: { padding: 4 },
    selectionHeader: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
    },
    selectionHeaderTitle: {
      flex: 1,
      textAlign: "center",
      fontSize: 16,
      fontWeight: "700",
      color: theme.text,
    },
    selectionHeaderAction: { paddingHorizontal: 4, paddingVertical: 2 },
    selectionHeaderActionText: { fontSize: 15, fontWeight: "600", color: theme.primary },
    searchBar: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      backgroundColor: theme.surface,
      borderRadius: 12,
      paddingHorizontal: 12,
      paddingVertical: 8,
    },
    searchInput: {
      flex: 1,
      fontSize: 16,
      color: theme.text,
      paddingVertical: 0,
      minHeight: 22,
    },
    searchCancel: { paddingLeft: 4 },
    searchCancelText: { fontSize: 15, fontWeight: "600", color: theme.primary },
    todosLink: {
      flexDirection: "row",
      alignItems: "center",
      marginHorizontal: 14,
      marginBottom: 4,
      paddingHorizontal: 14,
      paddingVertical: 10,
      gap: 10,
    },
    // Same primary ink for Learning / Lists / Reminders (and chat rows below).
    todosLinkText: { flex: 1, fontSize: 15, fontWeight: "600", color: theme.text },
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
      fontSize: 11,
      fontWeight: "700",
      color: theme.textTertiary,
      textTransform: "uppercase",
      letterSpacing: 0.8,
      paddingHorizontal: 14,
      marginBottom: 2,
    },
    sectionHeader: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      marginTop: 18,
      paddingHorizontal: 14,
      paddingVertical: 4,
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
      paddingHorizontal: 14,
      paddingTop: 12,
      backgroundColor: "transparent",
    },
    footerNewChat: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      paddingVertical: 8,
      paddingHorizontal: 10,
      borderRadius: 10,
      backgroundColor: theme.primary,
    },
    footerNewChatText: { fontSize: 14, fontWeight: "600", color: theme.onPrimary },
    settingsBtn: {
      marginLeft: "auto",
      padding: 8,
      borderRadius: 10,
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
      paddingHorizontal: 14,
      paddingTop: 12,
      backgroundColor: theme.bg,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
    },
    selectionAction: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      paddingVertical: 8,
      paddingHorizontal: 12,
    },
    selectionActionDisabled: {
      opacity: 0.45,
    },
    selectionActionText: {
      fontSize: 15,
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
