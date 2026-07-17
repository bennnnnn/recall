import { useEffect, useRef } from "react";
import { Animated, Easing, Pressable, StyleSheet, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

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
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!recording) {
      pulse.stopAnimation();
      pulse.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 700,
          easing: Easing.out(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: 700,
          easing: Easing.in(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [recording, pulse]);

  const ringScale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.45],
  });
  const ringOpacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.55, 0],
  });

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
            style={[
              styles.ring,
              {
                borderColor: theme.primary,
                opacity: ringOpacity,
                transform: [{ scale: ringScale }],
              },
            ]}
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
