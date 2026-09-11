import { type ComponentProps } from "react";
import { type AccessibilityActionEvent, StyleSheet, View } from "react-native";
import { GestureDetector } from "react-native-gesture-handler";
import Animated, { type AnimatedStyle } from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { Radius } from "@/lib/radius";
import { shadowElevated } from "@/lib/shadow";
import { Theme, useTheme, withAlpha } from "@/lib/theme";

type AnimStyle = AnimatedStyle<Record<string, unknown>>;
type DetectorGesture = ComponentProps<typeof GestureDetector>["gesture"];

type Props = {
  regionGesture: DetectorGesture;
  cornerTL: DetectorGesture;
  cornerTR: DetectorGesture;
  cornerBL: DetectorGesture;
  cornerBR: DetectorGesture;
  regionStyle: AnimStyle;
  maskTopStyle: AnimStyle;
  maskBottomStyle: AnimStyle;
  maskLeftStyle: AnimStyle;
  maskRightStyle: AnimStyle;
  handleTLStyle: AnimStyle;
  handleTRStyle: AnimStyle;
  handleBLStyle: AnimStyle;
  handleBRStyle: AnimStyle;
  onGrow: () => void;
  onShrink: () => void;
};

export function MathScannerCropOverlay({
  regionGesture,
  cornerTL,
  cornerTR,
  cornerBL,
  cornerBR,
  regionStyle,
  maskTopStyle,
  maskBottomStyle,
  maskLeftStyle,
  maskRightStyle,
  handleTLStyle,
  handleTRStyle,
  handleBLStyle,
  handleBRStyle,
  onGrow,
  onShrink,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);

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
        >
          <View style={s.cornerTL} />
          <View style={s.cornerTR} />
          <View style={s.cornerBL} />
          <View style={s.cornerBR} />
        </Animated.View>
      </GestureDetector>
      <GestureDetector gesture={cornerTL}>
        <Animated.View style={[s.handle, handleTLStyle]} accessible={false} />
      </GestureDetector>
      <GestureDetector gesture={cornerTR}>
        <Animated.View style={[s.handle, handleTRStyle]} accessible={false} />
      </GestureDetector>
      <GestureDetector gesture={cornerBL}>
        <Animated.View style={[s.handle, handleBLStyle]} accessible={false} />
      </GestureDetector>
      <GestureDetector gesture={cornerBR}>
        <Animated.View style={[s.handle, handleBRStyle]} accessible={false} />
      </GestureDetector>
    </View>
  );
}

function makeStyles(theme: Theme) {
  const corner = {
    position: "absolute" as const,
    width: 24,
    height: 24,
    borderColor: theme.primary,
  };
  return StyleSheet.create({
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
      borderColor: withAlpha(theme.onMedia, 0.95),
      borderWidth: 2,
      borderRadius: Radius.sm,
      backgroundColor: "transparent",
      zIndex: 4,
      ...shadowElevated(theme, "fab"),
    },
    handle: {
      position: "absolute",
      zIndex: 8,
    },
    cornerTL: { ...corner, top: -2, left: -2, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 6 },
    cornerTR: { ...corner, top: -2, right: -2, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 6 },
    cornerBL: { ...corner, bottom: -2, left: -2, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 6 },
    cornerBR: { ...corner, bottom: -2, right: -2, borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 6 },
  });
}
