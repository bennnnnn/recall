import { StyleSheet } from "react-native";

import { Space } from "@/lib/space";
import { type Theme } from "@/lib/theme";
import { Type } from "@/lib/type";

/** Shared by Settings home and its submenus so their row styles stay aligned. */
export function makeSettingsStyles(theme: Theme) {
  return StyleSheet.create({
    center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.bg },
    root: { flex: 1, backgroundColor: theme.bg },
    scroll: { flex: 1, backgroundColor: theme.bg },
    content: {
      paddingHorizontal: Space.gutter,
      paddingTop: Space.xs,
      paddingBottom: Space.xl + Space.xs,
    },
    section: { marginTop: Space.xl },
    sectionLabel: {
      ...Type.body,
      fontSize: 17,
      color: theme.textSecondary,
      marginHorizontal: Space.gutter,
      marginBottom: Space.sm,
    },
    footerGroup: {
      backgroundColor: theme.bg,
      borderRadius: 28,
      overflow: "hidden",
    },
    overviewCard: { gap: 2 },
    menuRow: {
      flexDirection: "row",
      alignItems: "center",
      minHeight: 68,
      paddingHorizontal: Space.gutter,
      paddingVertical: Space.gutter,
      gap: Space.gutter,
      borderRadius: 4,
      backgroundColor: theme.settingsSurface,
    },
    rowPressed: { opacity: 0.65 },
    rowBody: { flex: 1, gap: 2 },
    rowTitle: { ...Type.body, fontSize: 18, color: theme.text },
    meta: { ...Type.callout, fontWeight: "400", color: theme.textSecondary },
    linkValue: { ...Type.callout, fontWeight: "400", color: theme.textSecondary },
    linkTrailing: { flexDirection: "row", alignItems: "center", gap: Space.xs },
    menuSeparator: { height: 2, backgroundColor: theme.bg },
    usageTrack: {
      height: 6,
      borderRadius: 3,
      backgroundColor: theme.border,
      overflow: "hidden",
      marginTop: Space.xs,
    },
    usageFill: { height: 6, borderRadius: 3, backgroundColor: theme.primary },
  });
}

export type SettingsStyles = ReturnType<typeof makeSettingsStyles>;
