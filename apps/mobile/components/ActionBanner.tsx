import { useEffect, useMemo, useRef } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import Animated, {
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Motion } from "@/lib/motion";
import { Theme, useTheme, withAlpha } from "@/lib/theme";

type Props = {
  message: string | null;
  icon?: keyof typeof Ionicons.glyphMap;
  onDismiss: () => void;
  bottomOffset?: number;
};

const SHOW_MS = 2600;

export function ActionBanner({
  message,
  icon = "checkmark-circle",
  onDismiss,
  bottomOffset = 24,
}: Props) {
  const insets = useSafeAreaInsets();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const opacity = useSharedValue(0);
  const translateY = useSharedValue(24);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!message) return;

    opacity.value = 0;
    translateY.value = 24;
    opacity.value = withTiming(1, { duration: Motion.duration.snappy });
    translateY.value = withSpring(0, { damping: 14, stiffness: 140 });

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      opacity.value = withTiming(0, { duration: Motion.duration.snappy }, (finished) => {
        if (finished) runOnJS(onDismiss)();
      });
      translateY.value = withTiming(16, { duration: Motion.duration.snappy });
    }, SHOW_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [message, onDismiss, opacity, translateY]);

  const bannerStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ translateY: translateY.value }],
  }));

  if (!message) return null;

  const toastText = theme.isDark ? theme.text : theme.onPrimary;

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
          <Pressable style={s.toast} onPress={onDismiss}>
            <Ionicons name={icon} size={18} color={toastText} />
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
      borderRadius: 999,
      paddingHorizontal: 20,
      paddingVertical: 14,
      maxWidth: 340,
      borderWidth: theme.isDark ? StyleSheet.hairlineWidth : 0,
      borderColor: theme.border,
      boxShadow: `0 8 24 0 ${withAlpha(theme.scrim, 0.45)}`,
      elevation: 16,
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
