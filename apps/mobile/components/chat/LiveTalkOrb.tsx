import { useEffect, useMemo } from "react";
import { StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import Animated, {
  Easing,
  type SharedValue,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { type LiveTalkPhase } from "@/lib/liveTalkLogic";
import { Motion } from "@/lib/motion";
import { Theme } from "@/lib/theme";

const ORB = 220;

type Props = {
  theme: Theme;
  phase: LiveTalkPhase;
  meterLevel: number;
  recording: boolean;
  reduceMotion: boolean;
};

/** Fixed circle with a moving cloud inside — the rim does not scale. */
export function LiveTalkOrb({ theme, phase, meterLevel, recording, reduceMotion }: Props) {
  const s = useMemo(() => makeOrbStyles(), []);
  const voice = useSharedValue(0.2);
  const pulse = useSharedValue(0.2);
  const listening = useSharedValue(recording ? 1 : 0);
  const drift = useSharedValue(0);

  useEffect(() => {
    listening.value = withTiming(recording ? 1 : 0, { duration: 80 });
  }, [listening, recording]);

  useEffect(() => {
    voice.value = withTiming(Math.max(0.2, meterLevel), { duration: 70 });
  }, [voice, meterLevel]);

  useEffect(() => {
    if (reduceMotion) {
      pulse.value = phase === "speaking" ? 0.55 : 0.22;
      return;
    }
    if (phase === "speaking") {
      pulse.value = withRepeat(
        withSequence(
          withTiming(0.95, { duration: 320, easing: Motion.easing.inOut }),
          withTiming(0.4, { duration: 320, easing: Motion.easing.inOut }),
        ),
        -1,
        false,
      );
      return;
    }
    if (phase === "thinking") {
      pulse.value = withRepeat(
        withSequence(
          withTiming(0.48, { duration: Motion.duration.soft, easing: Motion.easing.inOut }),
          withTiming(0.22, { duration: Motion.duration.soft, easing: Motion.easing.inOut }),
        ),
        -1,
        false,
      );
      return;
    }
    pulse.value = withRepeat(
      withSequence(
        withTiming(0.3, { duration: 1400, easing: Motion.easing.inOut }),
        withTiming(0.14, { duration: 1400, easing: Motion.easing.inOut }),
      ),
      -1,
      false,
    );
  }, [pulse, phase, reduceMotion]);

  useEffect(() => {
    if (reduceMotion) {
      drift.value = 0.35;
      return;
    }
    drift.value = 0;
    drift.value = withRepeat(withTiming(1, { duration: 4200, easing: Easing.linear }), -1, false);
  }, [drift, reduceMotion]);

  const cloudA = useBlobStyle(drift, voice, pulse, listening, 1, 22, 18);
  const cloudB = useBlobStyle(drift, voice, pulse, listening, 1.35, -26, 20);
  const cloudC = useBlobStyle(drift, voice, pulse, listening, 0.8, 14, -24);

  const inner = theme.isDark
    ? ([theme.primaryDark, theme.primary, theme.primaryLight] as const)
    : ([theme.primaryLight, theme.primary, theme.primary] as const);
  const mid = theme.isDark
    ? ([theme.primary, theme.primaryDark, theme.bg] as const)
    : ([theme.primaryLight, theme.primary, theme.primaryDark] as const);
  const shine = theme.isDark
    ? ([theme.primaryDark, theme.primaryLight] as const)
    : ([theme.bg, theme.primaryLight] as const);

  return (
    <View style={[s.orbClip, { backgroundColor: theme.primaryLight }]}>
      <Animated.View style={[s.blob, s.blobA, cloudA]}>
        <LinearGradient
          colors={[...inner]}
          start={{ x: 0.1, y: 0 }}
          end={{ x: 0.9, y: 1 }}
          style={s.fill}
        />
      </Animated.View>
      <Animated.View style={[s.blob, s.blobB, cloudB]}>
        <LinearGradient
          colors={[...mid]}
          start={{ x: 0.2, y: 1 }}
          end={{ x: 0.8, y: 0 }}
          style={s.fill}
        />
      </Animated.View>
      <Animated.View style={[s.blob, s.blobC, cloudC]}>
        <LinearGradient
          colors={[...shine]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={s.fill}
        />
      </Animated.View>
    </View>
  );
}

function useBlobStyle(
  drift: SharedValue<number>,
  voice: SharedValue<number>,
  pulse: SharedValue<number>,
  listening: SharedValue<number>,
  speed: number,
  ampX: number,
  ampY: number,
) {
  return useAnimatedStyle(() => {
    const t = drift.value * Math.PI * 2 * speed;
    const agitate =
      0.38 + voice.value * 0.9 * listening.value + pulse.value * (1 - listening.value);
    return {
      transform: [
        { translateX: Math.cos(t) * ampX * agitate },
        { translateY: Math.sin(t * 1.2) * ampY * agitate },
        { scale: 0.78 + agitate * 0.48 },
      ],
    };
  });
}

function makeOrbStyles() {
  return StyleSheet.create({
    orbClip: {
      width: ORB,
      height: ORB,
      borderRadius: ORB / 2,
      overflow: "hidden",
    },
    blob: {
      position: "absolute",
      borderRadius: 999,
    },
    blobA: {
      width: ORB * 0.92,
      height: ORB * 0.92,
      left: -ORB * 0.12,
      top: ORB * 0.08,
    },
    blobB: {
      width: ORB * 0.78,
      height: ORB * 0.78,
      right: -ORB * 0.18,
      top: -ORB * 0.1,
    },
    blobC: {
      width: ORB * 0.48,
      height: ORB * 0.48,
      left: ORB * 0.28,
      bottom: -ORB * 0.06,
      opacity: 0.7,
    },
    fill: {
      width: "100%",
      height: "100%",
      borderRadius: 999,
    },
  });
}
