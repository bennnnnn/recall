import { Pressable, StyleSheet, Text } from "react-native";

import { StrokeIcon, type StrokeIconName } from "@/components/StrokeIcons";
import { Theme } from "@/lib/theme";

/** Shared icon size for attach + chat/drawer action sheets. */
export const ACTION_SHEET_ICON_SIZE = 20;

type Props = {
  icon: StrokeIconName;
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
      <StrokeIcon name={icon} size={ACTION_SHEET_ICON_SIZE} color={color} />
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
      paddingVertical: 16,
      gap: 14,
    },
    itemPressed: {
      backgroundColor: C.surfaceAlt,
    },
    label: {
      fontSize: 17,
      color: C.text,
      fontWeight: "400",
      flex: 1,
    },
    labelDanger: {
      color: C.danger,
    },
  });
}
