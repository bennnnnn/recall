import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Theme } from "@/lib/theme";

/** Shared icon size for attach + chat/drawer action sheets. */
export const ACTION_SHEET_ICON_SIZE = 20;

type Props = {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  theme: Theme;
  /** Hairline above this row (skip on the first item). */
  showDivider?: boolean;
  danger?: boolean;
};

/**
 * One icon+label row for floating action sheets (attach, chat ⋮, drawer).
 * Keep chrome identical across call sites — same size, padding, dividers.
 */
export function ActionSheetRow({
  icon,
  label,
  onPress,
  theme,
  showDivider = false,
  danger = false,
}: Props) {
  const s = makeStyles(theme);
  const color = danger ? theme.danger : theme.text;

  return (
    <>
      {showDivider ? <View style={s.divider} /> : null}
      <Pressable
        style={({ pressed }) => [s.item, pressed && s.itemPressed]}
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel={label}
      >
        <Ionicons name={icon} size={ACTION_SHEET_ICON_SIZE} color={color} />
        <Text style={[s.label, danger && s.labelDanger]}>{label}</Text>
      </Pressable>
    </>
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
    divider: {
      height: StyleSheet.hairlineWidth,
      backgroundColor: C.border,
      marginLeft: 52,
    },
  });
}
