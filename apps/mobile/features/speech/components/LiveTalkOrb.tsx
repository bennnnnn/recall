import { useEffect, useMemo } from "react";
import { StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";

import { liveTalkOrbMode, type LiveTalkPhase } from "@/features/speech/model/liveTalkLogic";
import {
  BLINK_CLOSE_MS,
  BLINK_OPEN_MS,
  BLINK_SHUT_SCALE,
  scheduleBlinks,
} from "@/features/speech/model/orbBlink";
import { Motion } from "@/lib/motion";
import { Theme } from "@/lib/theme";
import { Space } from "@/lib/space";
import { Radius } from "@/lib/radius";

/** Room around the face, so its swell while speaking never touches anything. */
const STAGE = 236;
const CORE = 128;
/** The face's gentle swell while the reply's voice plays: 1.00 to 1.05 and back. */
const SPEAK_SCALE = 1.05;
const SPEAK_BREATH_MS = 620;
/** How long the face takes to settle back to rest when the voice stops. */
const SPEAK_SETTLE_MS = 280;

type Props = {
  theme: Theme;
  phase: LiveTalkPhase;
  /** The reply's audio is playing on the phone: the only time the face moves. */
  speaking: boolean;
  reduceMotion: boolean;
};

/**
 * The live talk face: a still orb with two eyes that look straight ahead and blink now
 * and then. It swells softly only while Recall's voice is playing; there is no halo or
 * ring. With reduce motion on, nothing moves and the eyes do not blink.
 */
export function LiveTalkOrb({ theme, phase, speaking, reduceMotion }: Props) {
  const s = useMemo(() => makeOrbStyles(theme), [theme]);
  const mode = liveTalkOrbMode(phase);
  const scale = useSharedValue(1);
  const blink = useSharedValue(1);

  // Each change starts from where the face is, so speech starts and stops without a jump.
  useEffect(() => {
    cancelAnimation(scale);
    if (reduceMotion) {
      scale.value = 1;
      return;
    }
    const ease = Motion.easing.inOut;
    scale.value = speaking
      ? withRepeat(
          withSequence(
            withTiming(SPEAK_SCALE, { duration: SPEAK_BREATH_MS, easing: ease }),
            withTiming(1, { duration: SPEAK_BREATH_MS, easing: ease }),
          ),
          -1,
          false,
        )
      : withTiming(1, { duration: SPEAK_SETTLE_MS, easing: ease });
  }, [reduceMotion, scale, speaking]);

  useEffect(() => {
    cancelAnimation(blink);
    blink.value = 1;
    if (reduceMotion) return;
    const ease = Motion.easing.inOut;
    return scheduleBlinks(() => {
      blink.value = withSequence(
        withTiming(BLINK_SHUT_SCALE, { duration: BLINK_CLOSE_MS, easing: ease }),
        withTiming(1, { duration: BLINK_OPEN_MS, easing: ease }),
      );
    });
  }, [blink, reduceMotion]);

  const faceStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const eyesStyle = useAnimatedStyle(() => ({ transform: [{ scaleY: blink.value }] }));

  const inner = theme.isDark
    ? ([theme.primaryDark, theme.primary, theme.primaryLight] as const)
    : ([theme.primary, theme.primaryDark] as const);

  return (
    <View style={s.stage} testID={`live-talk-orb-${mode}`}>
      <Animated.View style={[s.core, faceStyle]} testID="live-talk-orb-face">
        <LinearGradient colors={[...inner]} start={{ x: 0.22, y: 0 }} end={{ x: 0.85, y: 1 }} style={s.fill} />
        <Animated.View style={[s.eyes, eyesStyle]} testID="live-talk-orb-eyes">
          <View style={s.eye} />
          <View style={s.eye} />
        </Animated.View>
      </Animated.View>
    </View>
  );
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
    eyes: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      marginTop: -14,
    },
    eye: {
      width: 11,
      height: 24,
      borderRadius: Radius.full,
      // The eyes sit mid-orb, on the accent: white on indigo (5.5:1), and near-black
      // on dark mode's pale accent (10:1), where white was 1.9:1.
      backgroundColor: theme.onPrimary,
    },
  });
}
