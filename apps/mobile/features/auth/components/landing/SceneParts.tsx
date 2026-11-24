/**
 * The pieces every landing scene is built from: a card that frames it, chat bubbles, and
 * `Reveal`, which brings its child in at its step once the scene is on screen. A scene off
 * screen starts over, so each one plays from the top when it is swiped to; under Reduce
 * Motion every step is shown at once, still.
 */
import { createContext, type ReactNode, useContext, useEffect, useMemo } from "react";
import { type StyleProp, StyleSheet, Text, type TextProps, useWindowDimensions, View, type ViewStyle } from "react-native";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withTiming,
} from "react-native-reanimated";

import { Motion, useReduceMotion } from "@/lib/motion";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

/** The time between one step of a scene and the next. */
const SCENE_STEP_MS = 700;
/** How far a step rises as it fades in. */
const RISE = 10;

export function Reveal({
  active,
  step,
  children,
  style,
}: {
  active: boolean;
  step: number;
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  const reduceMotion = useReduceMotion();
  const shown = useSharedValue(reduceMotion ? 1 : 0);

  useEffect(() => {
    cancelAnimation(shown);
    if (reduceMotion) {
      shown.value = 1;
      return;
    }
    if (!active) {
      shown.value = 0;
      return;
    }
    shown.value = withDelay(
      step * SCENE_STEP_MS,
      withTiming(1, { duration: Motion.duration.short, easing: Motion.easing.out }),
    );
  }, [active, reduceMotion, shown, step]);

  const animated = useAnimatedStyle(() => ({
    opacity: shown.value,
    transform: [{ translateY: (1 - shown.value) * RISE }],
  }));
  return <Animated.View style={[style, animated]}>{children}</Animated.View>;
}

/** The slide's colour, set by the showcase: each feature plays on its own field. */
export const SceneTint = createContext<string | null>(null);

/** The card a scene plays in, drawn as an app screen on its slide's colour field. */
export function SceneCard({ children }: { children: ReactNode }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const tint = useContext(SceneTint) ?? theme.primary;
  const { height } = useWindowDimensions();
  return (
    <View
      style={[
        s.field,
        { height: sceneHeight(height), backgroundColor: withAlpha(tint, theme.isDark ? 0.22 : 0.14) },
      ]}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <View style={s.card}>
        <View style={[s.grabber, { backgroundColor: withAlpha(tint, 0.35) }]} />
        {children}
      </View>
    </View>
  );
}

/** Words inside a scene are part of its picture: they keep their size under large system
 * text, so a scene never outgrows its card (the titles and words under it still scale). */
export function SceneText(props: TextProps) {
  return <Text maxFontSizeMultiplier={1} {...props} />;
}

export function UserBubble({ text }: { text: string }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={s.userBubble}>
      <SceneText style={s.userText}>{text}</SceneText>
    </View>
  );
}

/** A line of the reply, as the chat draws one: plain text on the page. */
export function ReplyLine({ text, strong = false }: { text: string; strong?: boolean }) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return <SceneText style={[s.reply, strong && s.replyStrong]}>{text}</SceneText>;
}

/** What the landing needs besides the scene (headline, title, words, dots, button, system
 * bars), measured on a 727 dp tall Galaxy S23 where a 340 dp scene just fits. */
const LANDING_CHROME = 390;
const SCENE_MIN = 240;
const SCENE_MAX = 380;

/** The scene takes the room the screen has, so the landing fits without scrolling from a
 * 640 dp phone to a tablet; below the minimum the landing scrolls instead. */
export function sceneHeight(windowHeight: number): number {
  return Math.min(SCENE_MAX, Math.max(SCENE_MIN, windowHeight - LANDING_CHROME));
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    field: { borderRadius: Radius.xl, padding: Space.md, paddingBottom: 0 },
    card: {
      flex: 1,
      borderTopLeftRadius: Radius.xl,
      borderTopRightRadius: Radius.xl,
      backgroundColor: theme.elevated,
      paddingHorizontal: Space.gutter,
      paddingTop: Space.sm,
      gap: Space.sm,
      overflow: "hidden",
    },
    grabber: { alignSelf: "center", width: 36, height: Space.xxs, borderRadius: Radius.full, marginBottom: Space.xxs },
    userBubble: {
      alignSelf: "flex-end",
      maxWidth: "85%",
      backgroundColor: theme.userBubble,
      borderRadius: Radius.lg,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
    },
    userText: { ...Type.secondary, color: theme.userText },
    reply: { ...Type.secondary, color: theme.text },
    replyStrong: { ...Weight.semibold },
  });
}
