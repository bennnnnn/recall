import { Pressable, StyleSheet, Text } from "react-native";

import { Icon } from "@/ui/icons/Icon";
import type { IconName } from "@/ui/icons/names";
import { Theme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Space } from "@/lib/space";
import { IconSize } from "@/ui/icons/sizes";

/** Shared icon size for attach + chat/drawer action sheets. */
export const ACTION_SHEET_ICON_SIZE = IconSize.sm;

type Props = {
  icon: IconName;
  label: string;
  onPress: () => void;
  theme: Theme;
  danger?: boolean;
};

/**
 * One icon+label row for floating action sheets (attach, chat ⋮, drawer).
 * Keep chrome identical across call sites — same size and padding; no dividers.
 */
export function ActionSheetRow({
  icon,
  label,
  onPress,
  theme,
  danger = false,
}: Props) {
  const s = makeStyles(theme);
  const color = danger ? theme.danger : theme.text;

  return (
    <Pressable
      style={({ pressed }) => [s.item, pressed && s.itemPressed]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <Icon name={icon} size={ACTION_SHEET_ICON_SIZE} color={color} />
      <Text style={[s.label, danger && s.labelDanger]}>{label}</Text>
    </Pressable>
  );
}

export function makeActionSheetPanelStyle(theme: Theme) {
  return {
    backgroundColor: theme.inputBg,
  };
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    item: {
      flexDirection: "row",
      alignItems: "center",
      paddingHorizontal: 18,
      paddingVertical: Space.md,
      gap: 14,
    },
    itemPressed: {
      backgroundColor: C.surfaceAlt,
    },
    label: {
      ...Type.navTitle,
      ...Weight.regular,
      color: C.text,
      flex: 1,
    },
    labelDanger: {
      color: C.danger,
    },
  });
}
