import { useMemo, type ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Icon } from "@/components/Icon";
import { type IoniconName } from "@/lib/icons";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type SettingsOverviewGroupProps = {
  label?: string;
  children: ReactNode;
};

type SettingsOverviewRowProps = {
  icon: IoniconName;
  title: string;
  value?: string;
  onPress?: () => void;
  accessibilityHint?: string;
  expanded?: boolean;
  danger?: boolean;
  accent?: boolean;
};

export function SettingsOverviewGroup({ label, children }: SettingsOverviewGroupProps) {
  const theme = useTheme();
  const styles = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={styles.group}>
      {label ? <Text style={styles.groupLabel}>{label}</Text> : null}
      <View style={styles.card}>{children}</View>
    </View>
  );
}

export function SettingsOverviewRow({
  icon,
  title,
  value,
  onPress,
  accessibilityHint,
  expanded,
  danger,
  accent,
}: SettingsOverviewRowProps) {
  const theme = useTheme();
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const color = danger ? theme.danger : accent ? theme.primary : theme.text;
  const accessibilityLabel = value ? `${title}, ${value}` : title;
  const content = (
    <>
      <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <Icon name={icon} size={26} color={color} />
      </View>
      <View style={styles.rowBody}>
        <Text style={[styles.title, { color }]}>{title}</Text>
        {value ? <Text style={styles.value}>{value}</Text> : null}
      </View>
    </>
  );

  if (!onPress) {
    return (
      <View
        style={styles.row}
        accessible
        accessibilityRole="text"
        accessibilityLabel={accessibilityLabel}
        accessibilityHint={accessibilityHint}
      >
        {content}
      </View>
    );
  }

  return (
    <Pressable
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityHint={accessibilityHint}
      accessibilityState={expanded === undefined ? undefined : { expanded }}
    >
      {content}
    </Pressable>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    group: {
      marginTop: Space.xl,
    },
    groupLabel: {
      ...Type.body,
      fontSize: 17,
      color: theme.textSecondary,
      marginHorizontal: Space.gutter,
      marginBottom: Space.sm,
    },
    card: {
      borderRadius: 28,
      overflow: "hidden",
      backgroundColor: theme.bg,
      gap: 2,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      minHeight: 68,
      paddingHorizontal: Space.gutter,
      paddingVertical: Space.gutter,
      gap: Space.gutter,
      borderRadius: 4,
      backgroundColor: theme.settingsSurface,
    },
    rowPressed: {
      opacity: 0.65,
    },
    rowBody: {
      flex: 1,
      gap: 2,
    },
    title: {
      ...Type.body,
      fontSize: 18,
    },
    value: {
      ...Type.callout,
      fontWeight: "400",
      color: theme.textSecondary,
    },
  });
}
