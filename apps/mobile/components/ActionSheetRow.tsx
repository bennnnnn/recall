import { Image, Pressable, StyleSheet, Text, type ImageSourcePropType } from "react-native";

import { Icon } from "@/ui/icons/Icon";
import { type IoniconName } from "@/lib/icons";
import { Theme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Space } from "@/lib/space";

/** Shared icon size for attach + chat/drawer action sheets. */
export const ACTION_SHEET_ICON_SIZE = 20;

type Props = {
  icon: IoniconName;
  /** Artwork from the product icons, tinted to the row color. */
  image?: ImageSourcePropType;
  /** Keep the artwork's own colors. The PDF mark has white letters. */
  preserveImageColor?: boolean;
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
  image,
  preserveImageColor = false,
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
      {image ? (
        <Image
          source={image}
          style={[s.glyph, preserveImageColor ? null : { tintColor: color }]}
          resizeMode="contain"
        />
      ) : (
        <Icon name={icon} size={ACTION_SHEET_ICON_SIZE} color={color} />
      )}
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
    glyph: {
      width: ACTION_SHEET_ICON_SIZE,
      height: ACTION_SHEET_ICON_SIZE,
    },
    label: {
      ...Type.navTitle,
      fontWeight: "400",
      color: C.text,
      flex: 1,
    },
    labelDanger: {
      color: C.danger,
    },
  });
}
