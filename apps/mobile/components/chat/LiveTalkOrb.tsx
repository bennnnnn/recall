import { useEffect, useMemo } from "react";
import { StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import Animated, {
  Easing,
  type SharedValue,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { liveTalkOrbMode, type LiveTalkPhase } from "@/lib/liveTalkLogic";
import { Motion } from "@/lib/motion";
import { Theme } from "@/lib/theme";

const STAGE = 236;
const CORE = 128;
const BAR_COUNT = 5;
const RING_COUNT = 3;

type Props = {
  theme: Theme;
  phase: LiveTalkPhase;
  meterLevel: number;
  recording: boolean;
  reduceMotion: boolean;
};

export function LiveTalkOrb({ theme, phase, meterLevel, reduceMotion }: Props) {
  const s = useMemo(() => makeOrbStyles(theme), [theme]);
  const mode = liveTalkOrbMode(phase);
  const wave = useSharedValue(0);
  const meter = useSharedValue(Math.max(0.12, meterLevel));
  const corePulse = useSharedValue(1);

  useEffect(() => {
    meter.value = withTiming(Math.max(0.12, meterLevel), { duration: 70 });
  }, [meter, meterLevel]);

  useEffect(() => {
    if (reduceMotion) {
      wave.value = 0.45;
      corePulse.value = mode === "speak" ? 1.04 : 1;
      return;
    }
    const duration = mode === "listen" ? 900 : mode === "speak" ? 720 : 1600;
    wave.value = 0;
    wave.value = withRepeat(withTiming(1, { duration, easing: Easing.linear }), -1, false);
    if (mode === "speak") {
      corePulse.value = withRepeat(
        withSequence(
          withTiming(1.06, { duration: 360, easing: Motion.easing.inOut }),
          withTiming(1, { duration: 360, easing: Motion.easing.inOut }),
        ),
        -1,
        false,
      );
      return;
    }
    corePulse.value = withTiming(1, { duration: 180 });
  }, [corePulse, mode, reduceMotion, wave]);

  const coreStyle = useAnimatedStyle(() => ({
    transform: [{ scale: corePulse.value }],
  }));

  const inner = theme.isDark
    ? ([theme.primaryDark, theme.primary, theme.primaryLight] as const)
    : ([theme.primary, theme.primaryDark] as const);

  return (
    <View style={s.stage} testID={`live-talk-orb-${mode}`}>
      <IntroBurst color={theme.primary} reduceMotion={reduceMotion} />
      {Array.from({ length: RING_COUNT }, (_, index) => (
        <PulseRing
          key={index}
          index={index}
          mode={mode}
          color={theme.primary}
          reduceMotion={reduceMotion}
        />
      ))}
      <Animated.View style={[s.core, coreStyle]}>
        <LinearGradient colors={[...inner]} start={{ x: 0.2, y: 0 }} end={{ x: 0.85, y: 1 }} style={s.fill} />
        <View style={s.bars}>
          {Array.from({ length: BAR_COUNT }, (_, index) => (
            <VoiceBar
              key={index}
              index={index}
              mode={mode}
              wave={wave}
              meter={meter}
              color={theme.onPrimary}
              reduceMotion={reduceMotion}
            />
          ))}
        </View>
      </Animated.View>
    </View>
  );
}

function IntroBurst({ color, reduceMotion }: { color: string; reduceMotion: boolean }) {
  const progress = useSharedValue(reduceMotion ? 1 : 0);
  useEffect(() => {
    if (reduceMotion) return;
    progress.value = 0;
    progress.value = withTiming(1, { duration: 640, easing: Motion.easing.out });
  }, [progress, reduceMotion]);
  const style = useAnimatedStyle(() => ({
    transform: [{ scale: 0.72 + progress.value * 0.95 }],
    opacity: (1 - progress.value) * 0.4,
  }));
  if (reduceMotion) return null;
  return <Animated.View pointerEvents="none" style={[ringBox(), { borderColor: color }, style]} />;
}

function PulseRing({
  index,
  mode,
  color,
  reduceMotion,
}: {
  index: number;
  mode: ReturnType<typeof liveTalkOrbMode>;
  color: string;
  reduceMotion: boolean;
}) {
  const progress = useSharedValue(reduceMotion ? 0.35 : 0);
  const listen = mode === "listen";
  const speak = mode === "speak";
  useEffect(() => {
    if (reduceMotion) {
      progress.value = 0.35;
      return;
    }
    progress.value = 0;
    const duration = listen ? 1280 : speak ? 980 : 1800;
    progress.value = withDelay(
      index * 240,
      withRepeat(withTiming(1, { duration, easing: Easing.linear }), -1, false),
    );
  }, [index, listen, progress, reduceMotion, speak]);

  const style = useAnimatedStyle(() => {
    const p = progress.value;
    if (listen) {
      return {
        transform: [{ scale: 1.52 - p * 0.62 }],
        opacity: (1 - p) * 0.48,
      };
    }
    if (speak) {
      return {
        transform: [{ scale: 1 + p * 0.58 }],
        opacity: (1 - p) * 0.52,
      };
    }
    const breathe = 1.08 + Math.sin(p * Math.PI * 2) * 0.06;
    return {
      transform: [{ scale: breathe }],
      opacity: 0.14 + (1 - p) * 0.12,
    };
  });

  return <Animated.View pointerEvents="none" style={[ringBox(), { borderColor: color }, style]} />;
}

function VoiceBar({
  index,
  mode,
  wave,
  meter,
  color,
  reduceMotion,
}: {
  index: number;
  mode: ReturnType<typeof liveTalkOrbMode>;
  wave: SharedValue<number>;
  meter: SharedValue<number>;
  color: string;
  reduceMotion: boolean;
}) {
  const style = useAnimatedStyle(() => {
    const center = (BAR_COUNT - 1) / 2;
    const dist = Math.abs(index - center) / Math.max(center, 1);
    const w = wave.value;
    let level = 0.18;
    if (mode === "listen") {
      const jitter = Math.sin(w * Math.PI * 2 * 2.2 + index * 1.35) * 0.5 + 0.5;
      level = 0.2 + meter.value * (0.35 + 0.65 * jitter) * (1 - dist * 0.32);
    } else if (mode === "speak") {
      const tone = Math.sin(w * Math.PI * 2 + index * 0.7) * 0.5 + 0.5;
      level = 0.28 + 0.72 * tone * (1 - dist * 0.22);
    } else if (mode === "think") {
      const sweep = w * (BAR_COUNT + 2) - 1;
      level = 0.12 + 0.7 * Math.max(0, 1 - Math.abs(index - sweep) / 1.5);
    } else {
      level = 0.16 + Math.sin(w * Math.PI * 2 + index) * 0.06;
    }
    if (reduceMotion) {
      level = mode === "speak" ? 0.55 - dist * 0.18 : mode === "listen" ? 0.4 - dist * 0.12 : 0.22;
    }
    const height = 8 + 36 * Math.max(0.08, Math.min(1, level));
    return { height, opacity: 0.45 + 0.55 * Math.min(1, level) };
  });
  return <Animated.View style={[barBox(color), style]} />;
}

function ringBox() {
  return {
    position: "absolute" as const,
    width: STAGE,
    height: STAGE,
    borderRadius: STAGE / 2,
    borderWidth: 2,
  };
}

function barBox(color: string) {
  return {
    width: 5,
    borderRadius: 3,
    backgroundColor: color,
  };
}

function makeOrbStyles(theme: Theme) {
  return StyleSheet.create({
    stage: {
      width: STAGE,
      height: STAGE,
      alignItems: "center",
      justifyContent: "center",
    },
    core: {
      width: CORE,
      height: CORE,
      borderRadius: CORE / 2,
      overflow: "hidden",
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.primary,
    },
    fill: {
      ...StyleSheet.absoluteFill,
    },
    bars: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 5,
      height: 48,
    },
  });
}
