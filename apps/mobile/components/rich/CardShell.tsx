import { ReactNode, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { Icon } from "@/components/Icon";
import { CopyButton } from "@/components/CopyButton";
import { type IoniconName } from "@/lib/icons";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  label: string;
  copyText?: string;
  icon?: IoniconName;
  iconColor?: string;
  accentColor?: string;
  /** When false, the left edge is a normal hairline — no colored stripe. */
  accent?: boolean;
  /** Extra header controls (edit, Gmail, …). Replaces the default Copy button. */
  headerActions?: ReactNode;
  children: ReactNode;
};

export function CardShell({
  label,
  copyText,
  icon,
  iconColor,
  accentColor,
  accent = true,
  headerActions,
  children,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const resolvedAccent = accentColor ?? theme.border;

  return (
    <View
      style={[
        s.wrap,
        accent ? { borderLeftColor: resolvedAccent } : s.wrapEven,
      ]}
    >
      <View style={s.header}>
        <View style={s.labelRow}>
          {icon ? <Icon name={icon} size={18} color={iconColor} /> : null}
          <Text style={s.label}>{label}</Text>
        </View>
        <View style={s.headerActions}>
          {headerActions ??
            (copyText ? <CopyButton text={copyText} /> : null)}
        </View>
      </View>
      <View style={s.body}>{children}</View>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      backgroundColor: t.surface,
      borderRadius: Radius.sheet,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      borderLeftWidth: 3,
      marginVertical: Space.xs,
      overflow: "hidden",
    },
    wrapEven: {
      borderLeftWidth: 1,
      borderLeftColor: t.border,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: Space.xs,
      paddingHorizontal: Space.sm,
      paddingTop: 10,
      paddingBottom: Space.xxs,
    },
    labelRow: { flexDirection: "row", alignItems: "center", gap: 6, flex: 1 },
    label: { fontSize: 13, fontWeight: "600", color: t.textSecondary },
    headerActions: { flexDirection: "row", alignItems: "center", gap: 2 },
    body: { paddingHorizontal: Space.sm, paddingVertical: 10 },
  });
}
