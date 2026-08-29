import { ReactNode, useMemo } from "react";
import { LayoutChangeEvent, StyleSheet, Text, View } from "react-native";

import { Icon } from "@/components/Icon";
import { type IoniconName } from "@/lib/icons";
import { radius, space } from "@/lib/layout";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  label: string;
  icon?: IoniconName;
  headerRight?: ReactNode;
  actions?: ReactNode;
  onLayout?: (event: LayoutChangeEvent) => void;
  children: ReactNode;
};

/** Shared chrome for chart / mermaid / chemistry visual cards. */
export function VisualCard({
  label,
  icon,
  headerRight,
  actions,
  onLayout,
  children,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.wrap} onLayout={onLayout}>
      <View style={s.header}>
        <View style={s.headerLeft}>
          {icon ? <Icon name={icon} size={16} color={theme.primary} /> : null}
          <Text style={s.headerLabel}>{label}</Text>
        </View>
        {headerRight}
      </View>
      {children}
      {actions ? <View style={s.actions}>{actions}</View> : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      marginVertical: space.sm,
      borderRadius: radius.lg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      overflow: "hidden",
      backgroundColor: t.bg,
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: 14,
      paddingVertical: 10,
      backgroundColor: t.surface,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
    },
    headerLeft: { flexDirection: "row", alignItems: "center", gap: space.sm },
    headerLabel: { ...Type.label, fontWeight: "700", color: t.text },
    actions: {
      flexDirection: "row",
      alignItems: "center",
      gap: space.xs,
      paddingHorizontal: space.sm,
      paddingVertical: space.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
    },
  });
}
