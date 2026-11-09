import { useMemo, type ReactNode } from "react";
import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from "react-native";

import { Icon } from "../icons/Icon";
import type { IconName } from "../icons/names";
import { IconSize } from "../icons/sizes";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  name?: IconName;
  /** Custom drawing (e.g. a BrandMark) — overrides `name` when set. */
  icon?: ReactNode;
  onPress: () => void;
  accessibilityLabel: string;
  size?: number;
  color?: string;
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
  style,
  testID,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      testID={testID}
      style={({ pressed }) => [s.hit, pressed && s.pressed, style]}
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
  });
}
