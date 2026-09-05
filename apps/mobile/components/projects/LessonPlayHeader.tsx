/* eslint-disable react-hooks/immutability -- Reanimated shared values are mutated on the UI thread by design */
import { useEffect, useRef } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withTiming,
} from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  current: number;
  total: number;
  fill: number;
  reviewing: boolean;
  onClose: () => void;
  onOpenMenu: () => void;
};

const TRACK = 10;
const SPARK = 10;

export function LessonPlayHeader({
  current,
  total,
  fill,
  reviewing,
  onClose,
  onOpenMenu,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);
  const reduceMotion = useReduceMotion();
  const progress = useSharedValue(fill);
  const spark = useSharedValue(0);
  const previousFill = useRef(fill);

  useEffect(() => {
    const advanced = fill > previousFill.current + 0.001;
    previousFill.current = fill;
    if (reduceMotion) {
      progress.value = fill;
      spark.value = 0;
      return;
    }
    progress.value = withTiming(fill, {
      duration: Motion.duration.short,
      easing: Motion.easing.out,
    });
    if (!advanced) return;
    spark.value = 0;
    spark.value = withSequence(
      withTiming(1, { duration: 90 }),
      withTiming(0, { duration: Motion.duration.snappy, easing: Motion.easing.out }),
    );
  }, [fill, progress, reduceMotion, spark]);

  const fillStyle = useAnimatedStyle(() => ({
    width: `${Math.max(0, Math.min(1, progress.value)) * 100}%`,
  }));
  const sparkStyle = useAnimatedStyle(() => ({
    opacity: spark.value,
    transform: [{ scale: 0.45 + spark.value * 0.7 }],
  }));

  return (
    <View style={s.wrap}>
      <View style={s.top}>
        <Pressable
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel={t("lesson.close")}
          hitSlop={8}
          style={s.iconBtn}
        >
          <Icon name="close" size={26} color={theme.text} />
        </Pressable>
        <Pressable
          onPress={onOpenMenu}
          accessibilityRole="button"
          accessibilityLabel={t("lesson.menu")}
          hitSlop={8}
          style={s.iconBtn}
        >
          <Icon name="ellipsis-vertical" size={22} color={theme.text} />
        </Pressable>
      </View>
      <View style={s.barRow}>
        <View
          style={s.track}
          accessible
          accessibilityRole="progressbar"
          accessibilityValue={{ min: 0, max: total, now: current }}
        >
          <Animated.View style={[s.fill, fillStyle]}>
            <Animated.View pointerEvents="none" style={[s.spark, sparkStyle]}>
              <View style={[s.dot, s.dotA]} />
              <View style={[s.dot, s.dotB]} />
              <View style={[s.dot, s.dotC]} />
            </Animated.View>
          </Animated.View>
        </View>
        <Text style={s.label}>
          {t(reviewing ? "lesson.review_of" : "lesson.step_of", { current, total })}
        </Text>
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      paddingHorizontal: Space.lg,
      paddingTop: Space.sm,
      paddingBottom: Space.md,
      gap: Space.sm,
    },
    top: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
    },
    iconBtn: {
      minWidth: Space.minTouch,
      minHeight: Space.minTouch,
      alignItems: "center",
      justifyContent: "center",
    },
    barRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
    },
    track: {
      flex: 1,
      height: TRACK,
      borderRadius: Radius.full,
      backgroundColor: theme.border,
      overflow: "visible",
      justifyContent: "center",
    },
    fill: {
      height: TRACK,
      borderRadius: Radius.full,
      backgroundColor: theme.primary,
    },
    spark: {
      position: "absolute",
      right: -5,
      top: (TRACK - SPARK) / 2,
      width: SPARK,
      height: SPARK,
    },
    label: {
      ...Type.caption,
      color: theme.textSecondary,
    },
    dot: {
      position: "absolute",
      width: 3,
      height: 3,
      borderRadius: 1.5,
      backgroundColor: theme.bg,
    },
    dotA: { top: 0, left: 3 },
    dotB: { top: 4, left: 7 },
    dotC: { top: 6, left: 1 },
  });
}
