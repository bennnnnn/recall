import { useMemo } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import { Theme, useTheme } from "@/lib/theme";

type Variant = "primary" | "outline" | "ghost";

type Props = {
  title: string;
  onPress: () => void;
  variant?: Variant;
  loading?: boolean;
  disabled?: boolean;
  accessibilityLabel?: string;
  /** Layout-only overrides (e.g. `{ flex: 1 }` in action rows). */
  style?: StyleProp<ViewStyle>;
};

/**
 * Shared primary CTA. Defaults: radius 12, minHeight 48, 16/700.
 * Leave specialized controls alone (send circle, pills, branded auth, soft LearningContinueCta).
 */
export function Button({
  title,
  onPress,
  variant = "primary",
  loading = false,
  disabled = false,
  accessibilityLabel,
  style,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const blocked = disabled || loading;

  return (
    <Pressable
      style={({ pressed }) => [
        s.base,
        variant === "primary" && s.primary,
        variant === "outline" && s.outline,
        variant === "ghost" && s.ghost,
        blocked && s.disabled,
        pressed && !blocked && s.pressed,
        style,
      ]}
      onPress={onPress}
      disabled={blocked}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? title}
      accessibilityState={{ disabled: blocked, busy: loading }}
    >
      {loading && variant === "primary" ? (
        <ActivityIndicator color={theme.onPrimary} />
      ) : (
        <Text
          style={[
            s.label,
            variant === "primary" && s.labelPrimary,
            variant === "outline" && s.labelOutline,
            variant === "ghost" && s.labelGhost,
          ]}
        >
          {title}
        </Text>
      )}
    </Pressable>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    base: {
      minHeight: 48,
      borderRadius: 12,
      paddingHorizontal: 18,
      paddingVertical: 12,
      alignItems: "center",
      justifyContent: "center",
    },
    primary: {
      backgroundColor: theme.primary,
    },
    outline: {
      backgroundColor: "transparent",
      borderWidth: 1,
      borderColor: theme.border,
    },
    ghost: {
      backgroundColor: "transparent",
      minHeight: undefined,
      paddingVertical: 10,
    },
    disabled: {
      opacity: 0.55,
    },
    pressed: {
      opacity: 0.85,
    },
    label: {
      fontSize: 16,
      fontWeight: "700",
    },
    labelPrimary: {
      color: theme.onPrimary,
    },
    labelOutline: {
      color: theme.textSecondary,
      fontWeight: "600",
    },
    labelGhost: {
      color: theme.primary,
      fontWeight: "600",
      fontSize: 15,
    },
  });
}
