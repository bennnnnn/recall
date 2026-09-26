import { useMemo } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import { ActionShimmer } from "../feedback/ActionShimmer";
import { Icon } from "../icons/Icon";
import type { IconName } from "../icons/names";
import { IconSize } from "../icons/sizes";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "destructive";
/** sm 36 (inline actions), md 44 (default), lg 52 (a screen's main action). */
type Size = "sm" | "md" | "lg";

type Props = {
  title: string;
  onPress: () => void;
  variant?: Variant;
  size?: Size;
  /** Icon beside the label, e.g. `arrow-right` on a get-started button. */
  icon?: IconName;
  iconPlacement?: "start" | "end";
  loading?: boolean;
  loadingLabel?: string;
  disabled?: boolean;
  accessibilityLabel?: string;
  /** Layout-only overrides (e.g. `{ flex: 1 }` in action rows). */
  style?: StyleProp<ViewStyle>;
};

/**
 * The app's button: a pill in five variants and three sizes, with an optional
 * leading icon. Leave specialized controls alone (send circle, branded auth,
 * the soft LearningContinueCta).
 */
export function Button({
  title,
  onPress,
  variant = "primary",
  size = "md",
  icon,
  iconPlacement = "start",
  loading = false,
  loadingLabel,
  disabled = false,
  accessibilityLabel,
  style,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const blocked = disabled || loading;
  const ink =
    variant === "primary" || variant === "destructive"
      ? theme.onPrimary
      : variant === "ghost"
        ? theme.primary
        : theme.textSecondary;

  return (
    <Pressable
      style={({ pressed }) => [
        s.base,
        size === "sm" && s.small,
        size === "lg" && s.large,
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
        <>
          {icon && iconPlacement === "start" ? <Icon name={icon} size={IconSize.sm} color={ink} /> : null}
          <Text
            style={[
              s.label,
              size === "sm" && s.labelSmall,
              size === "lg" && s.labelLarge,
              variant === "primary" && s.labelPrimary,
              (variant === "secondary" || variant === "outline") && s.labelOutline,
              variant === "ghost" && s.labelGhost,
              variant === "destructive" && s.labelPrimary,
            ]}
          >
            {title}
          </Text>
          {icon && iconPlacement === "end" ? <Icon name={icon} size={IconSize.sm} color={ink} /> : null}
        </>
      )}
    </Pressable>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    base: {
      minHeight: Space.minTouch,
      borderRadius: Radius.full,
      paddingHorizontal: Space.gutter,
      paddingVertical: Space.sm,
      flexDirection: "row",
      gap: Space.xs,
      alignItems: "center",
      justifyContent: "center",
    },
    small: {
      minHeight: Space.xl + Space.xxs,
      paddingHorizontal: Space.md,
      paddingVertical: Space.xs,
    },
    large: {
      minHeight: Space.xl + Space.gutter,
      paddingHorizontal: Space.lg,
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
      ...Type.body,
      ...Weight.semibold,
    },
    labelSmall: { ...Type.label, ...Weight.semibold },
    labelLarge: { ...Weight.bold },
    labelPrimary: {
      color: theme.onPrimary,
    },
    labelOutline: {
      color: theme.textSecondary,
      ...Weight.semibold,
    },
    labelGhost: {
      ...Type.callout,
      color: theme.primary,
    },
    loadingLabel: {
      ...Type.callout,
      ...Weight.bold,
    },
  });
}
