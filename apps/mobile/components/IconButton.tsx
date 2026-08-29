import { useMemo } from "react";
import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from "react-native";

import { Icon } from "@/components/Icon";
import { type IoniconName } from "@/lib/icons";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  name: IoniconName;
  onPress: () => void;
  accessibilityLabel: string;
  size?: number;
  color?: string;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
  testID?: string;
};

/** 44×44 hit target around a smaller outline icon. */
export function IconButton({
  name,
  onPress,
  accessibilityLabel,
  size = 20,
  color,
  disabled = false,
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
        pressed && !disabled && s.pressed,
        disabled && s.disabled,
        style,
      ]}
    >
      <Icon name={name} size={size} color={color} />
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
