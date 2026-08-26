import { useMemo } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import { ActionShimmer } from "@/components/ActionShimmer";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "destructive";

type Props = {
  title: string;
  onPress: () => void;
  variant?: Variant;
  loading?: boolean;
  loadingLabel?: string;
  disabled?: boolean;
  accessibilityLabel?: string;
  /** Layout-only overrides (e.g. `{ flex: 1 }` in action rows). */
  style?: StyleProp<ViewStyle>;
};

/**
 * Shared primary CTA. Defaults: Radius.md, minHeight 44, 16/600.
 * Leave specialized controls alone (send circle, pills, branded auth, soft LearningContinueCta).
 */
export function Button({
  title,
  onPress,
  variant = "primary",
  loading = false,
  loadingLabel,
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
        (variant === "secondary" || variant === "outline") && s.outline,
        variant === "ghost" && s.ghost,
        variant === "destructive" && s.destructive,
        blocked && s.disabled,
        pressed && !blocked && variant === "primary" && s.pressedPrimary,
        pressed && !blocked && variant === "destructive" && s.pressedDestructive,
        pressed && !blocked && variant !== "primary" && variant !== "destructive" && s.pressed,
        style,
      ]}
      onPress={onPress}
      disabled={blocked}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? (loading && loadingLabel ? loadingLabel : title)}
      accessibilityState={{ disabled: blocked, busy: loading }}
    >
      {loading && loadingLabel ? (
        <ActionShimmer
          label={loadingLabel}
          color={
            variant === "primary" || variant === "destructive" ? theme.onPrimary : theme.primary
          }
          compact
          delayMs={220}
          textStyle={s.loadingLabel}
        />
      ) : loading ? (
        <ActivityIndicator
          color={variant === "primary" || variant === "destructive" ? theme.onPrimary : theme.primary}
        />
      ) : (
        <Text
          style={[
            s.label,
            variant === "primary" && s.labelPrimary,
            (variant === "secondary" || variant === "outline") && s.labelOutline,
            variant === "ghost" && s.labelGhost,
            variant === "destructive" && s.labelPrimary,
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
      minHeight: 44,
      borderRadius: Radius.md,
      paddingHorizontal: Space.md,
      paddingVertical: Space.sm,
      alignItems: "center",
      justifyContent: "center",
    },
    primary: {
      backgroundColor: theme.primary,
    },
    outline: {
      backgroundColor: "transparent",
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    ghost: {
      backgroundColor: "transparent",
      minHeight: 44,
      paddingVertical: Space.xs,
    },
    destructive: {
      backgroundColor: theme.danger,
    },
    disabled: {
      opacity: 0.55,
    },
    pressed: {
      opacity: 0.72,
    },
    pressedPrimary: {
      backgroundColor: theme.primaryDark,
    },
    pressedDestructive: {
      opacity: 0.88,
    },
    label: {
      fontSize: 16,
      fontWeight: "600",
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
    loadingLabel: {
      fontSize: 15,
      fontWeight: "700",
    },
  });
}
