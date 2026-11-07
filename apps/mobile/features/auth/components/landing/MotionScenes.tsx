/**
 * Landing scenes that move: a photo of a problem scanned and solved, and a throw drawn as
 * the physics scenes draw one, its ball flying the arc again and again while the slide is
 * on screen. Under Reduce Motion the scan line and the ball keep still.
 */
import { useEffect, useMemo, useState } from "react";
import { Image, type LayoutChangeEvent, StyleSheet, Text, View } from "react-native";
import Animated, {
  cancelAnimation,
  useAnimatedProps,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withSequence,
  withTiming,
} from "react-native-reanimated";
import Svg, { Circle, Line, Path } from "react-native-svg";

import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Reveal, SceneCard } from "./SceneParts";

type SceneProps = { active: boolean };

const AnimatedCircle = Animated.createAnimatedComponent(Circle);
/** The pause after each pass before the scan line or the ball goes again. */
const REST_MS = 900;
const PAPER_HEIGHT = 130;
/** A photographed worksheet: "Solve for x: 3(x - 2) + 4 = 2x + 7", which works out to 9. */
const WORKSHEET = require("@/assets/images/landing-worksheet.jpg");

/** 0 to 1 over ``ms``, then a rest, again and again while ``active``; 0 when still. */
function useLoop(active: boolean, ms: number) {
  const reduceMotion = useReduceMotion();
  const progress = useSharedValue(0);
  useEffect(() => {
    cancelAnimation(progress);
    progress.value = 0;
    if (!active || reduceMotion) return;
    progress.value = withRepeat(
      withSequence(
        withTiming(0, { duration: 0 }),
        withTiming(1, { duration: ms, easing: Motion.easing.linear }),
        withDelay(REST_MS, withTiming(1, { duration: 0 })),
      ),
      -1,
    );
  }, [active, ms, progress, reduceMotion]);
  return { progress, still: reduceMotion };
}

export function ScanScene({ active }: SceneProps) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { progress, still } = useLoop(active, Motion.duration.trajectory);
  const sweep = useAnimatedStyle(() => ({
    opacity: still ? 0 : 1,
    transform: [{ translateY: progress.value * (PAPER_HEIGHT - 4) }],
  }));
  return (
    <SceneCard>
      <View style={s.paper}>
        <Image source={WORKSHEET} style={s.photo} resizeMode="cover" />
        {(["topLeft", "topRight", "bottomLeft", "bottomRight"] as const).map((corner) => (
          <View key={corner} style={[s.corner, s[corner]]} />
        ))}
        <Animated.View style={[s.sweep, sweep]} />
      </View>
      <Reveal active={active} step={2} style={s.solved}>
        <Icon name="camera" size={IconSize.sm} color={theme.primary} />
        <Text style={s.solvedMaths}>3x {"\u2212"} 2 = 2x + 7</Text>
      </Reveal>
      <Reveal active={active} step={3} style={s.solved}>
        <Icon name="check-circle" size={IconSize.sm} color={theme.success} />
        <Text style={[s.solvedMaths, s.answer]}>x = 9</Text>
      </Reveal>
    </SceneCard>
  );
}

const PAD = 14;

export function PhysicsScene({ active }: SceneProps) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const { progress, still } = useLoop(active, Motion.duration.trajectory);
  const { width, height } = size;
  const ground = height - PAD;
  const peak = height * 0.62;
  const left = PAD;
  const right = width - PAD;
  // The arc of a throw on level ground: a parabola from the launch point to where it lands.
  const arc = `M ${left} ${ground} Q ${(left + right) / 2} ${ground - 2 * peak} ${right} ${ground}`;
  const ball = useAnimatedProps(() => {
    const p = still ? 0.5 : progress.value;
    return { cx: left + p * (right - left), cy: ground - 4 * peak * p * (1 - p) };
  });
  const onLayout = (event: LayoutChangeEvent) => {
    const { width: w, height: h } = event.nativeEvent.layout;
    if (w !== width || h !== height) setSize({ width: w, height: h });
  };
  return (
    <SceneCard>
      <Text style={s.given}>v{"₀"} = 20 m/s {"·"} 45{"°"}</Text>
      <View style={s.plot} onLayout={onLayout}>
        {width > 0 ? (
          <Svg width={width} height={height}>
            <Line x1={0} y1={ground} x2={width} y2={ground} stroke={theme.borderStrong} strokeWidth={1.5} />
            <Path d={arc} stroke={theme.primary} strokeWidth={2} strokeDasharray="6 6" fill="none" opacity={0.5} />
            <AnimatedCircle animatedProps={ball} r={9} fill={theme.primary} />
          </Svg>
        ) : null}
      </View>
      <Reveal active={active} step={1}>
        <Text style={s.range}>R = 40.8 m</Text>
      </Reveal>
    </SceneCard>
  );
}

const CORNER = 18;

function makeStyles(theme: Theme) {
  const edge = { position: "absolute" as const, width: CORNER, height: CORNER, borderColor: theme.primary };
  return StyleSheet.create({
    paper: {
      height: PAPER_HEIGHT,
      borderRadius: Radius.md,
      backgroundColor: theme.surface,
      alignItems: "center",
      justifyContent: "center",
      overflow: "hidden",
    },
    corner: edge,
    topLeft: { top: 0, left: 0, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: Radius.md },
    topRight: { top: 0, right: 0, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: Radius.md },
    bottomLeft: { bottom: 0, left: 0, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: Radius.md },
    bottomRight: {
      bottom: 0,
      right: 0,
      borderBottomWidth: 3,
      borderRightWidth: 3,
      borderBottomRightRadius: Radius.md,
    },
    photo: { ...StyleSheet.absoluteFill, width: "100%", height: "100%" },
    sweep: {
      position: "absolute",
      top: 0,
      left: Space.sm,
      right: Space.sm,
      height: 3,
      borderRadius: 2,
      backgroundColor: theme.primary,
      opacity: 0.8,
    },
    solved: { flexDirection: "row", alignItems: "center", gap: Space.xs },
    solvedMaths: { ...Type.body, ...Weight.medium, color: theme.text },
    answer: { ...Weight.bold },
    given: { ...Type.secondary, ...Weight.medium, color: theme.textSecondary },
    plot: { flex: 1 },
    range: { ...Type.body, ...Weight.semibold, color: theme.text, textAlign: "center" },
  });
}
