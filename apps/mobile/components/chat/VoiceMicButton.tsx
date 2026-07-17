import { useEffect } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { Motion } from "@/lib/motion";
import { useTheme } from "@/lib/theme";

type Props = {
  recording: boolean;
  transcribing: boolean;
  disabled?: boolean;
  onPress: () => void;
};

export function VoiceMicButton({ recording, transcribing, disabled, onPress }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const pulse = useSharedValue(0);

  useEffect(() => {
    if (!recording) {
      pulse.value = 0;
      return;
    }
    pulse.value = withRepeat(
      withSequence(
        withTiming(1, {
          duration: Motion.duration.soft,
          easing: Motion.easing.out,
        }),
        withTiming(0, {
          duration: Motion.duration.soft,
          easing: Motion.easing.in,
        }),
      ),
      -1,
      false,
    );
  }, [recording, pulse]);

  const ringStyle = useAnimatedStyle(() => ({
    opacity: 0.55 * (1 - pulse.value),
    transform: [{ scale: 1 + pulse.value * 0.45 }],
  }));

  return (
    <Pressable
      style={[styles.hit, disabled && styles.dim]}
      onPress={onPress}
      disabled={disabled || transcribing}
      hitSlop={6}
      accessibilityRole="button"
      accessibilityLabel={t("chat.voice_a11y")}
      accessibilityHint={recording ? t("chat.voice_stop_hint") : t("chat.voice_start_hint")}
    >
      <View style={styles.slot}>
        {recording ? (
          <Animated.View
            pointerEvents="none"
            style={[styles.ring, { borderColor: theme.primary }, ringStyle]}
          />
        ) : null}
        <View
          style={[
            styles.btn,
            {
              borderColor: recording ? theme.primary : theme.border,
              backgroundColor: recording ? theme.primary : theme.surface,
            },
          ]}
        >
          <Ionicons
            name={recording ? "stop" : "mic-outline"}
            size={recording ? 16 : 22}
            color={recording ? theme.onPrimary : theme.primary}
          />
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hit: { width: 40, height: 40, alignItems: "center", justifyContent: "center" },
  dim: { opacity: 0.55 },
  slot: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  ring: {
    position: "absolute",
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 2,
  },
  btn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: StyleSheet.hairlineWidth,
  },
});
