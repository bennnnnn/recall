/* eslint-disable react-hooks/immutability -- Reanimated shared values are mutated on the UI thread by design */
import { useMemo } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Pressable as GHPressable } from "react-native-gesture-handler";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import type { EdgeInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { IconSize } from "@/lib/icons";
import { SCANNER_SHUTTER_PX, SCANNER_TOP_CONTROL_PX } from "@/lib/math/mathScannerRegion";
import { Motion, motionMs, useReduceMotion } from "@/lib/motion";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  insets: EdgeInsets;
  granted: boolean;
  preview: boolean;
  busy: boolean;
  torchOn: boolean;
  error: string | null;
  lastPhotoUri: string | null;
  onClose: () => void;
  onResetFrame: () => void;
  onToggleTorch: () => void;
  onOpenLibrary: () => void;
  onCapture: () => void;
  onRetake: () => void;
  onSolve: () => void;
};

export function MathScannerChrome({
  insets,
  granted,
  preview,
  busy,
  torchOn,
  error,
  lastPhotoUri,
  onClose,
  onResetFrame,
  onToggleTorch,
  onOpenLibrary,
  onCapture,
  onRetake,
  onSolve,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const shutterScale = useSharedValue(1);
  const pressMs = motionMs(Motion.duration.press, reduceMotion);

  const shutterStyle = useAnimatedStyle(() => ({
    transform: [{ scale: shutterScale.value }],
  }));

  const bottomPad = Math.max(insets.bottom, Space.md) + Space.sm;
  const errorBottom = bottomPad + SCANNER_SHUTTER_PX + Space.lg;

  return (
    <View style={s.root} pointerEvents="box-none">
      {!preview ? (
        <View style={[s.topBar, { paddingTop: insets.top + Space.xs }]}>
          <Pressable
            style={s.topBtn}
            onPress={onClose}
            hitSlop={20}
            testID="math-scanner-close"
            accessibilityRole="button"
            accessibilityLabel={t("common.close")}
          >
            <Icon name="close" size={IconSize.lg} color={theme.onMedia} />
          </Pressable>
          {granted ? (
            <>
              <Pressable
                style={s.topBtn}
                onPress={onResetFrame}
                accessibilityRole="button"
                accessibilityLabel={t("chat.math_scan_reset_frame")}
              >
                <Icon name="refresh-outline" size={IconSize.lg} color={theme.onMedia} />
              </Pressable>
              <Pressable
                style={[s.topBtn, torchOn ? s.torchOn : null]}
                onPress={onToggleTorch}
                accessibilityRole="button"
                accessibilityState={{ selected: torchOn }}
                accessibilityLabel={
                  torchOn ? t("chat.math_scan_torch_on_a11y") : t("chat.math_scan_torch_off_a11y")
                }
              >
                <Icon
                  name={torchOn ? "flashlight" : "flashlight-outline"}
                  size={IconSize.lg}
                  color={torchOn ? theme.primary : theme.onMedia}
                  style={s.torchIcon}
                />
              </Pressable>
            </>
          ) : (
            <View style={s.topBtn} />
          )}
        </View>
      ) : null}

      {error ? (
        <Text
          style={[s.error, { bottom: errorBottom }]}
          accessibilityLiveRegion="polite"
          accessibilityRole="alert"
        >
          {error}
        </Text>
      ) : null}

      {preview ? (
        <View style={[s.previewActions, { paddingBottom: bottomPad }]}>
          <GHPressable
            style={s.previewSecondary}
            onPress={onRetake}
            disabled={busy}
            accessibilityRole="button"
            accessibilityState={{ disabled: busy }}
            accessibilityLabel={t("chat.math_scan_retake")}
          >
            <Text style={s.previewSecondaryText}>{t("chat.math_scan_retake")}</Text>
          </GHPressable>
          <GHPressable
            style={s.previewPrimary}
            onPress={onSolve}
            disabled={busy}
            accessibilityRole="button"
            accessibilityState={{ disabled: busy, busy }}
            accessibilityLabel={t("chat.math_scan_solve")}
          >
            {busy ? (
              <ActivityIndicator color={theme.onPrimary} />
            ) : (
              <Text style={s.previewPrimaryText}>{t("chat.math_scan_solve")}</Text>
            )}
          </GHPressable>
        </View>
      ) : granted ? (
        <View style={[s.bottom, { paddingBottom: bottomPad }]}>
          <View style={s.bottomScrim} pointerEvents="none" />
          {!preview ? <Text style={s.hint}>{t("chat.math_scan_hint")}</Text> : null}
          <View style={s.controls}>
            <GHPressable
              style={s.photosBtn}
              onPress={onOpenLibrary}
              disabled={busy}
              testID="math-scanner-photos"
              accessibilityRole="button"
              accessibilityState={{ disabled: busy }}
              accessibilityLabel={t("chat.math_scan_photos_a11y")}
            >
              {lastPhotoUri ? (
                <Image source={{ uri: lastPhotoUri }} style={s.photosThumb} />
              ) : (
                <Icon name="images-outline" size={IconSize.lg} color={theme.onMedia} />
              )}
            </GHPressable>
            <GHPressable
              onPressIn={() => {
                shutterScale.value = withTiming(0.92, { duration: pressMs });
              }}
              onPressOut={() => {
                shutterScale.value = withTiming(1, { duration: pressMs });
              }}
              onPress={onCapture}
              disabled={busy}
              testID="math-scanner-shutter"
              accessibilityRole="button"
              accessibilityState={{ disabled: busy, busy }}
              accessibilityLabel={t("chat.math_scan_capture_a11y")}
            >
              <Animated.View style={[s.shutter, shutterStyle]}>
                {busy ? <ActivityIndicator color={theme.text} /> : <View style={s.shutterInner} />}
              </Animated.View>
            </GHPressable>
            <View style={s.photosBtn} />
          </View>
        </View>
      ) : null}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    root: {
      ...StyleSheet.absoluteFill,
      zIndex: 40,
    },
    topBar: {
      position: "absolute",
      top: 0,
      left: Space.md,
      right: Space.md,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      zIndex: 50,
    },
    topBtn: {
      width: SCANNER_TOP_CONTROL_PX,
      height: SCANNER_TOP_CONTROL_PX,
      borderRadius: Radius.full,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: withAlpha(theme.mediaScrim, 0.55),
    },
    torchOn: {
      backgroundColor: withAlpha(theme.primary, 0.22),
    },
    torchIcon: {
      transform: [{ rotate: "-45deg" }],
    },
    hint: {
      ...Type.caption,
      color: withAlpha(theme.onMedia, 0.9),
      textAlign: "center",
      marginBottom: Space.sm,
    },
    error: {
      position: "absolute",
      alignSelf: "center",
      left: Space.md,
      right: Space.md,
      color: theme.danger,
      backgroundColor: withAlpha(theme.mediaScrim, 0.65),
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
      borderRadius: Radius.xs,
      overflow: "hidden",
      zIndex: 10,
      textAlign: "center",
      ...Type.compact,
    },
    bottom: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      zIndex: 10,
    },
    bottomScrim: {
      ...StyleSheet.absoluteFill,
      backgroundColor: withAlpha(theme.mediaScrim, 0.45),
    },
    controls: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: Space.md,
    },
    photosBtn: {
      width: 72,
      height: SCANNER_TOP_CONTROL_PX,
      alignItems: "center",
      justifyContent: "center",
    },
    photosThumb: {
      width: Space.minTouch,
      height: Space.minTouch,
      borderRadius: Radius.sm,
      backgroundColor: withAlpha(theme.onMedia, 0.18),
    },
    shutter: {
      width: SCANNER_SHUTTER_PX,
      height: SCANNER_SHUTTER_PX,
      borderRadius: Radius.full,
      borderWidth: 4,
      borderColor: theme.onMedia,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: withAlpha(theme.onMedia, 0.18),
    },
    shutterInner: {
      width: 60,
      height: 60,
      borderRadius: Radius.full,
      backgroundColor: theme.onMedia,
    },
    previewActions: {
      position: "absolute",
      left: Space.md,
      right: Space.md,
      bottom: 0,
      flexDirection: "row",
      gap: Space.sm,
      zIndex: 10,
    },
    previewSecondary: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingVertical: 14,
      borderRadius: Radius.md,
      backgroundColor: withAlpha(theme.onMedia, 0.18),
      minHeight: Space.minTouch,
    },
    previewSecondaryText: {
      ...Type.label,
      color: theme.onMedia,
      fontWeight: "700",
    },
    previewPrimary: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingVertical: 14,
      borderRadius: Radius.md,
      backgroundColor: theme.primary,
      minHeight: Space.minTouch,
    },
    previewPrimaryText: {
      ...Type.label,
      color: theme.onPrimary,
      fontWeight: "700",
    },
  });
}
