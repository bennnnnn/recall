import { useEffect, useId, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
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
};

/**
 * ChatGPT-style image-gen waiting card: soft dotted surface + live status
 * text. Sized to the message image thumbnail so the real image swaps in
 * without a layout jump.
 */
export function ImageGenPlaceholder({ statusText }: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const reduceMotion = useReduceMotion();
  const { width, height } = useThumbnailSize();
  const s = useMemo(() => makeStyles(C, width, height), [C, width, height]);
  const patternId = useId().replace(/:/g, "");
  const labelOpacity = useSharedValue(1);

  useEffect(() => {
    if (reduceMotion) {
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
  }, [labelOpacity, reduceMotion]);

  const labelStyle = useAnimatedStyle(() => ({ opacity: labelOpacity.value }));
  const label = statusText?.trim() || t("chat.status.image_gen");

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
  });
}
