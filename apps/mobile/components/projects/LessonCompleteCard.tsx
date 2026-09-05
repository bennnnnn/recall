import { useEffect, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withSequence,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { notifySuccess } from "@/lib/haptics";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

const BURST = 280;
const ICON = 96;
const SPECKS = [
  { x: -92, y: -118, size: 12, delay: 0, rotate: 18 },
  { x: 88, y: -124, size: 10, delay: 30, rotate: -24 },
  { x: -28, y: -136, size: 14, delay: 10, rotate: 8 },
  { x: 24, y: -132, size: 11, delay: 50, rotate: 40 },
  { x: -118, y: -48, size: 13, delay: 20, rotate: -12 },
  { x: 122, y: -36, size: 12, delay: 40, rotate: 28 },
  { x: -104, y: 36, size: 10, delay: 70, rotate: 52 },
  { x: 110, y: 42, size: 14, delay: 55, rotate: -36 },
  { x: -64, y: -86, size: 9, delay: 15, rotate: -8 },
  { x: 70, y: -78, size: 11, delay: 65, rotate: 16 },
  { x: -78, y: 8, size: 12, delay: 85, rotate: 34 },
  { x: 82, y: 14, size: 13, delay: 25, rotate: -20 },
  { x: -46, y: 58, size: 10, delay: 95, rotate: 6 },
  { x: 52, y: 64, size: 12, delay: 45, rotate: -48 },
  { x: -8, y: -148, size: 15, delay: 5, rotate: 0 },
  { x: 12, y: 86, size: 11, delay: 75, rotate: 22 },
  { x: -132, y: -8, size: 9, delay: 35, rotate: 60 },
  { x: 136, y: 6, size: 10, delay: 80, rotate: -14 },
  { x: -38, y: -58, size: 8, delay: 100, rotate: 12 },
  { x: 44, y: -42, size: 9, delay: 60, rotate: -28 },
] as const;

export function LessonCompleteCard({
  title,
  reviewing,
  groupDone,
}: {
  title: string | null;
  reviewing: boolean;
  groupDone: boolean;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const scale = useSharedValue(reduceMotion ? 1 : 0.6);
  const opacity = useSharedValue(reduceMotion ? 1 : 0);
  const colors = [theme.success, theme.primary, theme.warning, theme.accent];

  useEffect(() => {
    notifySuccess();
    if (reduceMotion) return;
    scale.value = withSpring(1, { damping: 14, stiffness: 150 });
    opacity.value = withTiming(1, {
      duration: Motion.duration.snappy,
      easing: Motion.easing.out,
    });
  }, [opacity, reduceMotion, scale]);

  const iconAnim = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
    opacity: opacity.value,
  }));

  return (
    <View style={s.wrap} accessibilityRole="summary" accessibilityLiveRegion="polite">
      <View testID={groupDone ? "lesson-complete-burst" : "lesson-complete-mark"} style={s.burst}>
        {groupDone && !reduceMotion ? (
          <>
            <WooRing color={theme.success} delay={0} />
            <WooRing color={theme.primary} delay={90} />
            {SPECKS.map((speck, index) => (
              <GlitterSpeck
                key={`${speck.x}:${speck.y}`}
                speck={speck}
                color={colors[index % colors.length] ?? theme.success}
              />
            ))}
          </>
        ) : null}
        <Animated.View style={[s.iconWrap, iconAnim]}>
          <Icon name="checkmark-circle" size={56} color={theme.success} />
        </Animated.View>
      </View>
      <Animated.View style={iconAnim}>
        <Text style={s.title}>
          {t(
            reviewing
              ? "lesson.group_review_complete"
              : groupDone
                ? "lesson.group_complete"
                : "lesson.group_today_complete",
            { title: title?.trim() || t("lesson.this_group") },
          )}
        </Text>
      </Animated.View>
    </View>
  );
}

function WooRing({ color, delay }: { color: string; delay: number }) {
  const progress = useSharedValue(0);

  useEffect(() => {
    progress.value = withDelay(
      delay,
      withTiming(1, { duration: Motion.duration.breathe * 2, easing: Motion.easing.out }),
    );
  }, [delay, progress]);

  const style = useAnimatedStyle(() => ({
    opacity: (1 - progress.value) * 0.55,
    transform: [{ scale: 0.7 + progress.value * 1.7 }],
  }));

  return (
    <Animated.View
      pointerEvents="none"
      style={[
        {
          position: "absolute",
          width: ICON,
          height: ICON,
          borderRadius: ICON / 2,
          borderWidth: 4,
          borderColor: color,
        },
        style,
      ]}
    />
  );
}

function GlitterSpeck({
  speck,
  color,
}: {
  speck: (typeof SPECKS)[number];
  color: string;
}) {
  const x = useSharedValue(0);
  const y = useSharedValue(0);
  const fade = useSharedValue(0);
  const twinkle = useSharedValue(0.7);
  const spin = useSharedValue(0);

  useEffect(() => {
    x.value = withDelay(speck.delay, withSpring(speck.x, { damping: 11, stiffness: 120 }));
    y.value = withDelay(speck.delay, withSpring(speck.y, { damping: 11, stiffness: 120 }));
    fade.value = withDelay(
      speck.delay,
      withSequence(
        withTiming(1, { duration: 120 }),
        withTiming(1, { duration: 420 }),
        withTiming(0, { duration: 640, easing: Motion.easing.out }),
      ),
    );
    twinkle.value = withDelay(
      speck.delay,
      withSequence(withTiming(1.35, { duration: 180 }), withTiming(0.85, { duration: 900 })),
    );
    spin.value = withDelay(
      speck.delay,
      withTiming(speck.rotate, { duration: 720, easing: Motion.easing.out }),
    );
  }, [fade, speck, spin, twinkle, x, y]);

  const style = useAnimatedStyle(() => ({
    opacity: fade.value,
    transform: [
      { translateX: x.value },
      { translateY: y.value },
      { scale: twinkle.value },
      { rotate: `${spin.value}deg` },
    ],
  }));
  const pill = speck.size >= 12;

  return (
    <Animated.View
      pointerEvents="none"
      style={[
        {
          position: "absolute",
          width: pill ? speck.size + 6 : speck.size,
          height: pill ? Math.max(6, speck.size * 0.45) : speck.size,
          borderRadius: pill ? 3 : speck.size / 2,
          backgroundColor: color,
        },
        style,
      ]}
    />
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      gap: Space.md,
      paddingVertical: Space.xl,
      overflow: "visible",
    },
    burst: {
      width: BURST,
      height: BURST,
      alignItems: "center",
      justifyContent: "center",
      overflow: "visible",
    },
    iconWrap: {
      width: ICON,
      height: ICON,
      borderRadius: ICON / 2,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: theme.successLight,
    },
    title: {
      ...Type.body,
      fontSize: 20,
      fontWeight: "700",
      color: theme.text,
      textAlign: "center",
    },
  });
}
