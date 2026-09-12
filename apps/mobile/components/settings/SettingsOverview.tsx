import { useMemo, type ReactNode } from "react";
import { Pressable, Text, View } from "react-native";

import { Icon } from "@/components/Icon";
import { makeSettingsStyles } from "@/components/settings/settingsStyles";
import { type IoniconName } from "@/lib/icons";
import { useTheme } from "@/lib/theme";

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
  const styles = useMemo(() => makeSettingsStyles(theme), [theme]);

  return (
    <View style={styles.section}>
      {label ? <Text style={styles.sectionLabel}>{label}</Text> : null}
      <View style={[styles.footerGroup, styles.overviewCard]}>{children}</View>
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
  const styles = useMemo(() => makeSettingsStyles(theme), [theme]);
  const color = danger ? theme.danger : accent ? theme.primary : theme.text;
  const accessibilityLabel = value ? `${title}, ${value}` : title;
  const content = (
    <>
      <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <Icon name={icon} size={26} color={color} />
      </View>
      <View style={styles.rowBody}>
        <Text style={[styles.rowTitle, { color }]}>{title}</Text>
        {value ? <Text style={styles.linkValue}>{value}</Text> : null}
      </View>
    </>
  );

  if (!onPress) {
    return (
      <View
        style={styles.menuRow}
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
      style={({ pressed }) => [styles.menuRow, pressed && styles.rowPressed]}
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
