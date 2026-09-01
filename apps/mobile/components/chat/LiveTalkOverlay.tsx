import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import Animated, {
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { LiveTalkOrb } from "@/components/chat/LiveTalkOrb";
import { liveTalkOrbA11yKey, liveTalkOrbAction, type LiveTalkPhase } from "@/lib/liveTalkLogic";
import { liveTalkCueForVisibility, playLiveTalkCue } from "@/lib/liveTalkSfx";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Theme, useTheme } from "@/lib/theme";

const ENTER_SPRING = { damping: 16, stiffness: 210, mass: 0.78 };
const EXIT_MS = 280;
const EXIT_DROP_Y = 78;
const ENTER_SCALE = 0.16;

type Props = {
  visible: boolean;
  phase: LiveTalkPhase;
  meterLevel: number;
  recording: boolean;
  /** Leave this strip open so ChatHeader (hamburger / ⋮) stays tappable. */
  headerInset: number;
  /** Leave the real composer (type / attach) uncovered. */
  composerClearance: number;
  onToggle: () => void;
};

export function LiveTalkOverlay({
  visible,
  phase,
  meterLevel,
  recording,
  headerInset,
  composerClearance,
  onToggle,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const orbAction = liveTalkOrbAction(phase);
  const [mounted, setMounted] = useState(visible);
  const appear = useSharedValue(visible ? 1 : 0);
  const wasVisible = useRef(false);

  useEffect(() => {
    if (visible) {
      const cue = liveTalkCueForVisibility(visible, wasVisible.current);
      if (cue) playLiveTalkCue(cue);
      wasVisible.current = visible;
      setMounted(true);
      appear.value = reduceMotion ? 1 : withSpring(1, ENTER_SPRING);
      return;
    }
    const cue = liveTalkCueForVisibility(visible, wasVisible.current);
    if (cue) playLiveTalkCue(cue);
    wasVisible.current = false;
    if (reduceMotion) {
      appear.value = 0;
      setMounted(false);
      return;
    }
    appear.value = withTiming(0, { duration: EXIT_MS, easing: Motion.easing.in }, (finished) => {
      if (finished) runOnJS(setMounted)(false);
    });
  }, [appear, reduceMotion, visible]);

  const overlayStyle = useAnimatedStyle(() => ({
    opacity: appear.value,
  }));
  const orbWrapStyle = useAnimatedStyle(() => ({
    transform: [
      { translateY: (1 - appear.value) * EXIT_DROP_Y },
      { scale: ENTER_SCALE + (1 - ENTER_SCALE) * appear.value },
    ],
  }));

  if (!mounted) return null;

  const orb = (
    <LiveTalkOrb
      theme={theme}
      phase={phase}
      meterLevel={meterLevel}
      recording={recording}
      reduceMotion={reduceMotion}
    />
  );

  return (
    <Animated.View
      style={[s.overlay, overlayStyle, { top: headerInset, bottom: composerClearance }]}
      testID="live-talk-overlay"
      pointerEvents={visible ? "auto" : "none"}
    >
      <View style={s.body}>
        <Animated.View style={orbWrapStyle}>
          {orbAction === "none" ? (
            <View testID="live-talk-orb">{orb}</View>
          ) : (
            <Pressable
              onPress={onToggle}
              accessibilityRole="button"
              accessibilityLabel={t(liveTalkOrbA11yKey(phase))}
              testID="live-talk-orb"
            >
              {orb}
            </Pressable>
          )}
        </Animated.View>
      </View>
    </Animated.View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    overlay: {
      position: "absolute",
      left: 0,
      right: 0,
      zIndex: 120,
    },
    body: {
      flex: 1,
      backgroundColor: theme.bg,
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
