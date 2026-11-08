import { useEffect, useMemo, useState } from "react";
import { type AccessibilityActionEvent, StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { GestureDetector, type GestureType, type LegacyComposedGesture } from "react-native-gesture-handler";
import Animated, {
  cancelAnimation,
  type AnimatedStyle,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import type { ScanHandle } from "@/lib/math/scannerRegion";
import { Radius } from "@/lib/radius";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Theme, useTheme, withAlpha } from "@/lib/theme";

type AnimStyle = AnimatedStyle<Record<string, unknown>>;
type DetectorGesture = GestureType | LegacyComposedGesture;

export type LiveScanFrameStatus = "idle" | "detecting" | "ready";

/** An edge or corner of the frame to drag: its touch area and its resize gesture. */
type FrameHandle = { handle: ScanHandle; gesture: DetectorGesture; style: AnimStyle };

type Props = {
  regionGesture: DetectorGesture;
  handles: FrameHandle[];
  regionStyle: AnimStyle;
  maskTopStyle: AnimStyle;
  maskBottomStyle: AnimStyle;
  maskLeftStyle: AnimStyle;
  maskRightStyle: AnimStyle;
  scanning: boolean;
  liveStatus?: LiveScanFrameStatus;
  onGrow: () => void;
  onShrink: () => void;
};

export function MathScannerCropOverlay({
  regionGesture,
  handles,
  regionStyle,
  maskTopStyle,
  maskBottomStyle,
  maskLeftStyle,
  maskRightStyle,
  scanning,
  liveStatus = "idle",
  onGrow,
  onShrink,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const corners = s.corners[liveStatus];
  const [regionHeight, setRegionHeight] = useState(0);
  const shimmerProgress = useSharedValue(0);

  useEffect(() => {
    cancelAnimation(shimmerProgress);
    shimmerProgress.value = 0;
    if (!scanning || reduceMotion || regionHeight <= 0) return;
    shimmerProgress.value = withRepeat(
      withTiming(1, { duration: 1850, easing: Motion.easing.linear }),
      -1,
      false,
    );
    return () => cancelAnimation(shimmerProgress);
  }, [reduceMotion, regionHeight, scanning, shimmerProgress]);

  const shimmerStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: -18 + shimmerProgress.value * (regionHeight + 36) }],
  }));

  const onA11yAction = (event: AccessibilityActionEvent) => {
    if (event.nativeEvent.actionName === "increment") onGrow();
    if (event.nativeEvent.actionName === "decrement") onShrink();
  };

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="box-none">
      <View style={s.maskLayer} pointerEvents="none">
        <Animated.View style={[s.mask, s.maskTop, maskTopStyle]} />
        <Animated.View style={[s.mask, s.maskBottom, maskBottomStyle]} />
        <Animated.View style={[s.mask, s.maskSide, maskLeftStyle]} />
        <Animated.View style={[s.mask, s.maskSide, maskRightStyle]} />
      </View>
      <GestureDetector gesture={regionGesture}>
        <Animated.View
          testID={`math-scanner-frame-${liveStatus}`}
          style={[s.region, regionStyle]}
          collapsable={false}
          accessible
          accessibilityRole="adjustable"
          accessibilityLabel={t("chat.math_scan_frame_a11y")}
          accessibilityActions={[
            { name: "increment", label: t("chat.math_scan_frame_grow") },
            { name: "decrement", label: t("chat.math_scan_frame_shrink") },
          ]}
          onAccessibilityAction={onA11yAction}
          onLayout={(event) => setRegionHeight(event.nativeEvent.layout.height)}
        >
          {scanning ? (
            <View style={s.shimmerClip} pointerEvents="none">
              <Animated.View
                testID="math-scanner-shimmer"
                style={[s.shimmerBand, reduceMotion ? s.shimmerStatic : shimmerStyle]}
              >
                <LinearGradient
                  colors={[
                    "transparent",
                    withAlpha(theme.primary, 0.22),
                    withAlpha(theme.primary, 0.82),
                    withAlpha(theme.primary, 0.22),
                    "transparent",
                  ]}
                  locations={[0, 0.28, 0.5, 0.72, 1]}
                  start={{ x: 0, y: 0.5 }}
                  end={{ x: 1, y: 0.5 }}
                  style={StyleSheet.absoluteFill}
                />
              </Animated.View>
            </View>
          ) : null}
          <View style={corners.tl} />
          <View style={corners.tr} />
          <View style={corners.bl} />
          <View style={corners.br} />
        </Animated.View>
      </GestureDetector>
      {handles.map(({ handle, gesture, style }) => (
        <GestureDetector key={handle} gesture={gesture}>
          <Animated.View style={[s.handle, style]} testID={`math-scanner-handle-${handle}`} accessible={false} />
        </GestureDetector>
      ))}
    </View>
  );
}

/** How long a corner's arms are, at most; a small frame's are a third of its side. */
const CORNER_ARM = 28;

/**
 * The frame is its four corners, in the accent alone (a white outline with accent corners
 * was two colours, and a full rectangle the mask already draws). Steady text the live
 * reader is sure of makes them heavier.
 */
function cornerStyles(color: string, thick: number) {
  const arm = {
    position: "absolute" as const,
    width: "34%" as const,
    height: "34%" as const,
    maxWidth: CORNER_ARM,
    maxHeight: CORNER_ARM,
    borderColor: color,
  };
  const out = -thick / 2;
  return StyleSheet.create({
    tl: { ...arm, top: out, left: out, borderTopWidth: thick, borderLeftWidth: thick, borderTopLeftRadius: Radius.sm },
    tr: { ...arm, top: out, right: out, borderTopWidth: thick, borderRightWidth: thick, borderTopRightRadius: Radius.sm },
    bl: { ...arm, bottom: out, left: out, borderBottomWidth: thick, borderLeftWidth: thick, borderBottomLeftRadius: Radius.sm },
    br: { ...arm, bottom: out, right: out, borderBottomWidth: thick, borderRightWidth: thick, borderBottomRightRadius: Radius.sm },
  });
}

function makeStyles(theme: Theme) {
  const corners: Record<LiveScanFrameStatus, ReturnType<typeof cornerStyles>> = {
    idle: cornerStyles(theme.primary, 4),
    detecting: cornerStyles(theme.primary, 4),
    ready: cornerStyles(theme.primary, 6),
  };
  return { corners, ...StyleSheet.create({
    maskLayer: {
      ...StyleSheet.absoluteFill,
    },
    mask: {
      position: "absolute",
      backgroundColor: theme.scrim,
    },
    maskTop: {
      top: 0,
      left: 0,
      right: 0,
    },
    maskBottom: {
      left: 0,
      right: 0,
      bottom: 0,
    },
    maskSide: {
      left: 0,
    },
    region: {
      position: "absolute",
      borderRadius: Radius.sm,
      backgroundColor: "transparent",
      zIndex: 4,
    },
    shimmerClip: {
      ...StyleSheet.absoluteFill,
      overflow: "hidden",
      borderRadius: Radius.sm,
    },
    shimmerBand: {
      position: "absolute",
      left: 0,
      right: 0,
      top: 0,
      height: 18,
    },
    shimmerStatic: {
      top: "50%",
      opacity: 0.42,
      transform: [{ translateY: -9 }],
    },
    // Above the frame for touches. No elevation: Android drew a shadow through these
    // see-through areas, a dark band inside the frame's edges.
    handle: {
      position: "absolute",
      zIndex: 8,
    },
  }) };
}
