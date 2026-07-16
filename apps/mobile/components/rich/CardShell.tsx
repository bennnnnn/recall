import { ReactNode, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { CopyButton } from "@/components/CopyButton";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  label: string;
  copyText?: string;
  icon?: keyof typeof Ionicons.glyphMap;
  iconColor?: string;
  accentColor?: string;
  children: ReactNode;
};

export function CardShell({
  label,
  copyText,
  icon,
  iconColor,
  accentColor,
  children,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const resolvedIconColor = iconColor ?? theme.textSecondary;
  const resolvedAccent = accentColor ?? theme.border;

  return (
    <View style={[s.wrap, { borderLeftColor: resolvedAccent }]}>
      <View style={s.header}>
        <View style={s.labelRow}>
          {icon ? <Ionicons name={icon} size={15} color={resolvedIconColor} /> : null}
          <Text style={s.label}>{label}</Text>
        </View>
        {copyText ? <CopyButton text={copyText} /> : null}
      </View>
      <View style={s.body}>{children}</View>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      backgroundColor: t.bg,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: t.border,
      borderLeftWidth: 3,
      marginVertical: 8,
      overflow: "hidden",
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8,
      paddingHorizontal: 12,
      paddingVertical: 9,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
      backgroundColor: t.surface,
    },
    labelRow: { flexDirection: "row", alignItems: "center", gap: 6, flex: 1 },
    label: { fontSize: 13, fontWeight: "600", color: t.textSecondary },
    body: { paddingHorizontal: 12, paddingVertical: 10 },
  });
}
