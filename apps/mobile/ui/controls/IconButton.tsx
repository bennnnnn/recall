import { useMemo, type ReactNode } from "react";
import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from "react-native";

import { Icon } from "../icons/Icon";
import { IconSize, type IoniconName } from "@/lib/icons";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  name?: IoniconName;
  /** Custom glyph from `@/lib/icons` (e.g. MenuIcon) — overrides `name` when set. */
  icon?: ReactNode;
  onPress: () => void;
  accessibilityLabel: string;
  size?: number;
  color?: string;
  disabled?: boolean;
  /** Pressed feedback override (e.g. a background tint instead of opacity). */
  pressedStyle?: StyleProp<ViewStyle>;
  style?: StyleProp<ViewStyle>;
  testID?: string;
};

/** 44×44 hit target around a smaller outline icon. Prefer this over a
 *  one-off Pressable wrapping `Icon` for standalone chrome controls. */
export function IconButton({
  name,
  icon,
  onPress,
  accessibilityLabel,
  size = IconSize.sm,
  color,
  disabled = false,
  pressedStyle,
  style,
  testID,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled }}
      testID={testID}
      style={({ pressed }) => [
        s.hit,
        pressed && !disabled && (pressedStyle ?? s.pressed),
        disabled && s.disabled,
        style,
      ]}
    >
      {icon ?? (name ? <Icon name={name} size={size} color={color} /> : null)}
    </Pressable>
  );
}

function makeStyles(_theme: Theme) {
  return StyleSheet.create({
    hit: {
      minWidth: Space.minTouch,
      minHeight: Space.minTouch,
      alignItems: "center",
      justifyContent: "center",
    },
    pressed: { opacity: 0.7 },
    disabled: { opacity: 0.4 },
  });
}
