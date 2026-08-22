import { useEffect, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withSpring, withTiming } from "react-native-reanimated";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { notifySuccess } from "@/lib/haptics";
import { Motion, useReduceMotion } from "@/lib/motion";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export function LessonCompleteCard() {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const reduceMotion = useReduceMotion();
  const scale = useSharedValue(reduceMotion ? 1 : 0.6);
  const opacity = useSharedValue(reduceMotion ? 1 : 0);

  useEffect(() => {
    notifySuccess();
    if (reduceMotion) return;
    scale.value = withSpring(1, { damping: 14, stiffness: 150 });
    opacity.value = withTiming(1, {
      duration: Motion.duration.snappy,
      easing: Motion.easing.out,
    });
  }, [opacity, reduceMotion, scale]);

  const anim = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
    opacity: opacity.value,
  }));

  return (
    <Animated.View style={[s.wrap, anim]} accessibilityRole="summary" accessibilityLiveRegion="polite">
      <View style={s.iconWrap}>
        <Icon name="checkmark-circle" size={56} color={theme.success} />
      </View>
      <Text style={s.title}>{t("lesson.chapter_complete")}</Text>
    </Animated.View>
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
    },
    iconWrap: {
      width: 96,
      height: 96,
      borderRadius: 48,
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
