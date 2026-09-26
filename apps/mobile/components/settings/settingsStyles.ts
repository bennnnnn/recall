import { StyleSheet } from "react-native";

import { Radius } from "@/lib/radius";
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
      paddingHorizontal: Space.md,
      paddingTop: Space.xs,
      paddingBottom: Space.xl + Space.xs,
    },
    section: { marginTop: Space.lg },
    sectionLabel: {
      ...Type.secondary,
      color: theme.textSecondary,
      marginHorizontal: Space.md,
      marginBottom: Space.sm,
    },
    footerGroup: {
      backgroundColor: theme.bg,
      borderRadius: Radius.xl,
      overflow: "hidden",
    },
    overviewCard: { gap: 2 },
    menuRow: {
      flexDirection: "row",
      alignItems: "center",
      minHeight: 56,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      gap: Space.md,
      borderRadius: 4,
      backgroundColor: theme.settingsSurface,
    },
    rowPressed: { opacity: 0.65 },
    rowBody: { flex: 1, gap: 2 },
    rowTitle: { ...Type.body, color: theme.text },
    meta: { ...Type.secondary, color: theme.textSecondary },
    linkValue: { ...Type.secondary, color: theme.textSecondary },
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
