import { Pressable, StyleSheet, Switch, Text, type StyleProp, type ViewStyle } from "react-native";

import { selection } from "@/lib/haptics";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

/**
 * Shared label + switch row for non-settings surfaces (settings rows use
 * SettingsSwitchRow, which is wired to the settings group styles). The whole
 * row is the switch tap target; the Switch itself is display-only.
 */
export function SwitchRow({
  label,
  value,
  onValueChange,
  disabled,
  style,
}: {
  label: string;
  value: boolean;
  onValueChange: (next: boolean) => void;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const theme = useTheme();
  return (
    <Pressable
      style={[styles.row, style]}
      accessibilityRole="switch"
      accessibilityLabel={label}
      accessibilityState={{ checked: value, disabled: Boolean(disabled) }}
      disabled={disabled}
      onPress={() => {
        selection();
        onValueChange(!value);
      }}
    >
      <Text style={[styles.label, { color: theme.text }]}>{label}</Text>
      <Switch
        value={value}
        disabled={disabled}
        onValueChange={onValueChange}
        thumbColor={theme.bg}
        trackColor={{ false: theme.border, true: theme.primary }}
        pointerEvents="none"
        importantForAccessibility="no-hide-descendants"
        accessibilityElementsHidden
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    minHeight: Space.minTouch,
    gap: Space.md,
  },
  label: {
    ...Type.navTitle,
    flex: 1,
  },
});
