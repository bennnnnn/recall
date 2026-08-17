import { useEffect, useId, useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Defs, Pattern, Rect } from "react-native-svg";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { useThumbnailSize } from "@/components/ChatMessageImage";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Theme, useTheme, withAlpha } from "@/lib/theme";

type Props = {
  /** Rotating status line (e.g. "Creating image"). */
  statusText?: string | null;
  outcome?: "pending" | "canceled" | "failed";
  onRetry?: () => void;
};

/**
 * ChatGPT-style image-gen waiting card: soft dotted surface + live status
 * text. Sized to the message image thumbnail so the real image swaps in
 * without a layout jump.
 */
export function ImageGenPlaceholder({
  statusText,
  outcome = "pending",
  onRetry,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const reduceMotion = useReduceMotion();
  const { width, height } = useThumbnailSize();
  const s = useMemo(() => makeStyles(C, width, height), [C, width, height]);
  const patternId = useId().replace(/:/g, "");
  const labelOpacity = useSharedValue(1);
  const settled = outcome === "canceled" || outcome === "failed";

  useEffect(() => {
    if (reduceMotion || settled) {
      labelOpacity.value = 1;
      return;
    }
    labelOpacity.value = withRepeat(
      withSequence(
        withTiming(0.45, {
          duration: Motion.duration.soft,
          easing: Motion.easing.inOut,
        }),
        withTiming(1, {
          duration: Motion.duration.soft,
          easing: Motion.easing.inOut,
        }),
      ),
      -1,
      false,
    );
  }, [labelOpacity, reduceMotion, settled]);

  const labelStyle = useAnimatedStyle(() => ({ opacity: labelOpacity.value }));
  const label =
    statusText?.trim() ||
    (outcome === "canceled"
      ? t("chat.image_gen_canceled")
      : outcome === "failed"
        ? t("chat.image_gen_failed")
        : t("chat.status.image_gen"));

  return (
    <View style={s.wrap} accessibilityRole="text" accessibilityLabel={label}>
      <Svg width={width} height={height} style={StyleSheet.absoluteFill}>
        <Defs>
          <Pattern id={patternId} width={14} height={14} patternUnits="userSpaceOnUse">
            <Circle cx={2} cy={2} r={1.1} fill={withAlpha(C.textTertiary, 0.35)} />
          </Pattern>
        </Defs>
        <Rect width="100%" height="100%" fill={C.surfaceAlt} />
        <Rect width="100%" height="100%" fill={`url(#${patternId})`} />
      </Svg>
      <Animated.View style={[s.labelWrap, labelStyle]}>
        <Text style={s.label}>{label}</Text>
        {settled && onRetry ? (
          <Pressable
            onPress={onRetry}
            hitSlop={8}
            style={s.retry}
            accessibilityRole="button"
            accessibilityLabel={t("common.retry")}
          >
            <Text style={s.retryLabel}>{t("common.retry")}</Text>
          </Pressable>
        ) : null}
      </Animated.View>
    </View>
  );
}

function makeStyles(C: Theme, width: number, height: number) {
  return StyleSheet.create({
    wrap: {
      width,
      height,
      borderRadius: 22,
      overflow: "hidden",
      backgroundColor: C.surfaceAlt,
    },
    labelWrap: {
      position: "absolute",
      top: 16,
      left: 16,
      right: 16,
    },
    label: {
      fontSize: 15,
      fontWeight: "500",
      color: C.textSecondary,
    },
    retry: {
      alignSelf: "flex-start",
      marginTop: 10,
      paddingHorizontal: 12,
      paddingVertical: 6,
      borderRadius: 14,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    retryLabel: {
      fontSize: 14,
      fontWeight: "600",
      color: C.text,
    },
  });
}
