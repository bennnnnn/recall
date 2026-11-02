import { useEffect, useMemo, useState } from "react";
import { AccessibilityInfo, Keyboard, Pressable, StyleSheet, View } from "react-native";
import Animated, {
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { useDrawerOpen } from "@/contexts/DrawerContext";
import { LiveTalkCallControls } from "@/features/speech/components/LiveTalkCallControls";
import { LiveTalkOrb } from "@/features/speech/components/LiveTalkOrb";
import {
  liveTalkOrbA11yHintKey,
  liveTalkOrbA11yKey,
  liveTalkOrbAction,
  liveTalkPhaseA11yKey,
  type LiveTalkPhase,
} from "@/features/speech/model/liveTalkLogic";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";

const ENTER_MS = 200;
const EXIT_MS = 240;
/** The composer's own air above its bottom pad, so the pair sits where its row did. */
const CONTROLS_LIFT = Space.xs;

/** The call as the overlay reads it (useLiveTalk's state and actions). */
type LiveTalkCall = {
  phase: LiveTalkPhase;
  voicePlaying: boolean;
  muted: boolean;
  toggle: () => void | Promise<void>;
  toggleMute: () => void;
  close: () => void;
};

type Props = {
  visible: boolean;
  call: LiveTalkCall;
  /** Leave this strip open so ChatHeader (hamburger / ⋮) stays tappable; the drawer hides the header. */
  headerInset: number;
  /** The composer's resting bottom pad (home indicator or minimum). */
  bottomInset: number;
};

/**
 * The live talk screen, from connecting to hang-up: the face, and mute and end where
 * the composer row was. The composer is not drawn during a call, so nothing on screen
 * but end (✕) can end it. The screen fades in and out; it never slides or scales.
 */
export function LiveTalkOverlay({ visible, call, headerInset, bottomInset }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const reduceMotion = useReduceMotion();
  const drawerOpen = useDrawerOpen();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { phase } = call;
  const orbAction = liveTalkOrbAction(phase);
  const orbLabel = t(liveTalkOrbA11yKey(phase));
  const orbHint = liveTalkOrbA11yHintKey(phase);
  const [mounted, setMounted] = useState(visible);
  const appear = useSharedValue(visible ? 1 : 0);

  // The orb has no on-screen Listening or Speaking copy; a screen reader is
  // told each change instead, so a blind user knows when to talk.
  useEffect(() => {
    const key = visible ? liveTalkPhaseA11yKey(phase) : null;
    if (key) AccessibilityInfo.announceForAccessibility(t(key));
  }, [phase, t, visible]);

  useEffect(() => {
    if (visible) {
      // The composer steps aside for the call; its keyboard goes with it.
      Keyboard.dismiss();
      setMounted(true);
      appear.value = reduceMotion ? 1 : withTiming(1, { duration: ENTER_MS, easing: Motion.easing.out });
      return;
    }
    if (reduceMotion) {
      appear.value = 0;
      setMounted(false);
      return;
    }
    appear.value = withTiming(0, { duration: EXIT_MS, easing: Motion.easing.in }, (finished) => {
      if (finished) runOnJS(setMounted)(false);
    });
  }, [appear, reduceMotion, visible]);

  const overlayStyle = useAnimatedStyle(() => ({ opacity: appear.value }));

  if (!mounted) return null;

  const orb = (
    <LiveTalkOrb theme={theme} phase={phase} speaking={call.voicePlaying} reduceMotion={reduceMotion} />
  );

  return (
    <Animated.View
      style={[s.overlay, overlayStyle, { top: drawerOpen ? 0 : headerInset }]}
      testID="live-talk-overlay"
      pointerEvents={visible ? "auto" : "none"}
    >
      <View style={s.body}>
        {orbAction === "none" ? (
          <View accessible accessibilityLabel={orbLabel} testID="live-talk-orb">
            {orb}
          </View>
        ) : (
          <Pressable
            onPress={() => void call.toggle()}
            accessibilityRole="button"
            accessibilityLabel={orbLabel}
            accessibilityHint={orbHint ? t(orbHint) : undefined}
            testID="live-talk-orb"
          >
            {orb}
          </Pressable>
        )}
      </View>
      {drawerOpen ? null : (
        <View style={[s.controls, { paddingBottom: bottomInset + CONTROLS_LIFT }]}>
          <LiveTalkCallControls muted={call.muted} onMutePress={call.toggleMute} onClose={call.close} />
        </View>
      )}
    </Animated.View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    overlay: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      zIndex: 120,
      backgroundColor: theme.bg,
    },
    body: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
    },
    controls: {
      paddingTop: Space.xs,
      alignItems: "center",
    },
  });
}
