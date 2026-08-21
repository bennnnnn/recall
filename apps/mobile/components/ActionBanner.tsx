import { useEffect, useMemo, useRef } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import Animated, {
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon } from "@/components/Icon";
import { type IoniconName } from "@/lib/icons";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Radius } from "@/lib/radius";
import { shadowElevated } from "@/lib/shadow";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  message: string | null;
  icon?: IoniconName;
  tone?: ActionFeedbackTone;
  onDismiss: () => void;
  bottomOffset?: number;
};

export type ActionFeedbackTone = "success" | "info" | "warning" | "error";

const SHOW_MS = 2600;

export function ActionBanner({
  message,
  icon = "checkmark-circle",
  tone = "success",
  onDismiss,
  bottomOffset = 24,
}: Props) {
  const insets = useSafeAreaInsets();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const opacity = useSharedValue(0);
  const translateY = useSharedValue(24);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!message) return;

    opacity.value = reduceMotion ? 1 : 0;
    translateY.value = reduceMotion ? 0 : 24;
    if (!reduceMotion) {
      opacity.value = withTiming(1, { duration: Motion.duration.snappy });
      translateY.value = withSpring(0, { damping: 14, stiffness: 140 });
    }

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      if (reduceMotion) {
        onDismiss();
        return;
      }
      opacity.value = withTiming(0, { duration: Motion.duration.snappy }, (finished) => {
        if (finished) runOnJS(onDismiss)();
      });
      translateY.value = withTiming(16, { duration: Motion.duration.snappy });
    }, SHOW_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [message, onDismiss, opacity, reduceMotion, translateY]);

  const bannerStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ translateY: translateY.value }],
  }));

  if (!message) return null;

  const iconColor =
    tone === "error"
      ? theme.danger
      : tone === "warning"
        ? theme.warning
        : tone === "info"
          ? theme.primary
          : theme.success;

  return (
    <Modal visible transparent animationType="none" onRequestClose={onDismiss}>
      <View style={s.overlay} pointerEvents="box-none">
        <Animated.View
          style={[
            s.wrap,
            {
              bottom: insets.bottom + bottomOffset,
            },
            bannerStyle,
          ]}
          pointerEvents="box-none"
        >
          <Pressable
            style={s.toast}
            onPress={onDismiss}
            accessibilityRole="alert"
            accessibilityLiveRegion="polite"
            accessibilityLabel={message}
          >
            <Icon name={icon} size={18} color={iconColor} />
            <Text style={s.text} numberOfLines={2}>
              {message}
            </Text>
          </Pressable>
        </Animated.View>
      </View>
    </Modal>
  );
}

function makeStyles(theme: Theme) {
  const toastBg = theme.isDark ? theme.surfaceAlt : theme.text;
  const toastText = theme.isDark ? theme.text : theme.onPrimary;

  return StyleSheet.create({
    overlay: {
      flex: 1,
      justifyContent: "flex-end",
      alignItems: "center",
    },
    wrap: {
      position: "absolute",
      left: 24,
      right: 24,
      alignItems: "center",
      zIndex: 9999,
    },
    toast: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      backgroundColor: toastBg,
      borderRadius: Radius.full,
      paddingHorizontal: 20,
      paddingVertical: 14,
      maxWidth: 340,
      borderWidth: theme.isDark ? StyleSheet.hairlineWidth : 0,
      borderColor: theme.border,
      ...shadowElevated(theme, "toast"),
    },
    text: {
      flexShrink: 1,
      fontSize: 15,
      fontWeight: "600",
      color: toastText,
      textAlign: "center",
    },
  });
}
